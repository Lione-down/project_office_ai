import asyncio
from collections.abc import AsyncIterable
from hashlib import sha256
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.base import new_uuid7
from app.models.file_assets import FileAsset
from app.models.projects import Project
from app.services.asset_contracts import (
    AssetOperationError,
    AssetSummary,
    asset_summary,
    sanitize_filename,
    validate_file_signature,
    validate_file_type,
)
from app.storage.local import (
    LocalStorageAdapter,
    StorageOperationError,
    has_cleanup_failure,
    record_cleanup_failure,
)


_INCOMPLETE_UPLOAD_STATUSES = frozenset({"uploaded", "deleting"})


class AssetUploadService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: LocalStorageAdapter,
        *,
        max_file_bytes: int,
        max_image_bytes: int,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._max_file_bytes = max_file_bytes
        self._max_image_bytes = max_image_bytes

    async def find_replay(
        self, user_id: UUID, idempotency_key: str
    ) -> AssetSummary | None:
        key = idempotency_key.strip()
        if not key or len(key) > 128:
            raise AssetOperationError(
                "idempotency_key_invalid", "Idempotency-Key 无效", 422
            )
        existing = await self._find_idempotent_asset(user_id, key)
        if existing is None:
            return None
        self._ensure_replayable(existing)
        return asset_summary(existing)

    async def upload(
        self,
        *,
        user_id: UUID,
        project_id: UUID | None,
        filename: str,
        content_type: str,
        content: AsyncIterable[bytes],
        idempotency_key: str,
    ) -> AssetSummary:
        replay = await self.find_replay(user_id, idempotency_key)
        if replay is not None:
            return replay
        key = idempotency_key.strip()

        safe_filename = sanitize_filename(filename)
        normalized_mime, policy = validate_file_type(safe_filename, content_type)
        extension = safe_filename[safe_filename.rfind(".") :].lower()
        project = await self._resolve_upload_project(user_id, project_id)
        asset_id = new_uuid7()
        storage_key = self._storage.build_quarantine_key(user_id, asset_id, extension)
        checkpoint = FileAsset(
            id=asset_id,
            user_id=user_id,
            project_id=project.id,
            original_filename=safe_filename,
            file_category=policy.category,
            mime_type=normalized_mime,
            byte_size=0,
            sha256=sha256(b"").hexdigest(),
            storage_provider=self._storage.provider,
            storage_key=storage_key,
            processing_status="uploaded",
            idempotency_key=key,
        )
        checkpoint, is_created = await self._create_checkpoint(checkpoint)
        if not is_created:
            return asset_summary(checkpoint)

        max_bytes = (
            min(self._max_file_bytes, self._max_image_bytes)
            if policy.category == "image"
            else self._max_file_bytes
        )
        try:
            stored = await self._storage.write_quarantine(
                user_id=user_id,
                asset_id=asset_id,
                extension=extension,
                chunks=content,
                max_bytes=max_bytes,
            )
        except StorageOperationError as exception:
            if (
                exception.error_code == "quarantine_cleanup_failed"
                or has_cleanup_failure(exception)
            ):
                await self._best_effort_mark_checkpoint(asset_id, "deleting", exception)
            else:
                await self._best_effort_delete_checkpoint(asset_id, exception)
            raise self._translate_storage_error(exception) from exception
        except asyncio.CancelledError as exception:
            if has_cleanup_failure(exception):
                await asyncio.shield(
                    self._best_effort_mark_checkpoint(asset_id, "deleting", exception)
                )
            else:
                await asyncio.shield(
                    self._best_effort_delete_checkpoint(asset_id, exception)
                )
            raise
        except Exception as exception:
            if has_cleanup_failure(exception):
                await self._best_effort_mark_checkpoint(asset_id, "deleting", exception)
            else:
                await self._best_effort_delete_checkpoint(asset_id, exception)
            raise

        try:
            path = self._storage.resolve_asset_key(user_id, asset_id, storage_key)
            validate_file_signature(path, extension, policy)
        except (StorageOperationError, AssetOperationError) as exception:
            await self._cleanup_failed_upload(checkpoint, exception)
            raise AssertionError("cleanup helper must raise")

        try:
            return await self._finalize_checkpoint(
                asset_id, user_id, project.id, stored.byte_size, stored.sha256
            )
        except AssetOperationError as exception:
            await self._cleanup_failed_upload(checkpoint, exception)
            raise AssertionError("cleanup helper must raise")

    async def _create_checkpoint(self, asset: FileAsset) -> tuple[FileAsset, bool]:
        async with self._session_factory() as session:
            try:
                project = await self._owned_project(
                    session, asset.user_id, asset.project_id, True
                )
                if project.is_archived:
                    raise AssetOperationError(
                        "project_archived", "归档项目不能上传资产", 409
                    )
                session.add(asset)
                await session.commit()
                return asset, True
            except IntegrityError as exception:
                await session.rollback()
                existing = await self._find_idempotent_asset(
                    asset.user_id, asset.idempotency_key or ""
                )
                if existing is not None:
                    self._ensure_replayable(existing)
                    return existing, False
                raise AssetOperationError(
                    "asset_conflict", "资产写入发生冲突", 409
                ) from exception

    async def _finalize_checkpoint(
        self,
        asset_id: UUID,
        user_id: UUID,
        project_id: UUID,
        byte_size: int,
        digest: str,
    ) -> AssetSummary:
        async with self._session_factory() as session:
            try:
                project = await self._owned_project(session, user_id, project_id, True)
                if project.is_archived:
                    raise AssetOperationError(
                        "project_archived", "归档项目不能上传资产", 409
                    )
                asset = await session.get(FileAsset, asset_id, with_for_update=True)
                if asset is None or asset.user_id != user_id:
                    raise AssetOperationError(
                        "asset_checkpoint_missing", "资产上传记录不存在", 500
                    )
                asset.byte_size = byte_size
                asset.sha256 = digest
                asset.processing_status = "quarantined"
                await session.commit()
                return asset_summary(asset)
            except (Exception, asyncio.CancelledError) as primary_error:
                try:
                    await session.rollback()
                except (Exception, asyncio.CancelledError) as rollback_error:
                    primary_error.recovery_failure = True
                    primary_error.add_note(
                        "checkpoint finalization rollback failed: "
                        f"{type(rollback_error).__name__}"
                    )
                raise

    async def _cleanup_failed_upload(
        self,
        asset: FileAsset,
        original_error: StorageOperationError | AssetOperationError,
    ) -> None:
        try:
            self._storage.delete_asset(asset.user_id, asset.id, asset.storage_key)
        except StorageOperationError as cleanup_error:
            record_cleanup_failure(original_error, cleanup_error)
            await self._best_effort_mark_checkpoint(
                asset.id, "deleting", original_error
            )
            if isinstance(original_error, StorageOperationError):
                raise self._translate_storage_error(original_error) from original_error
            raise original_error
        await self._best_effort_delete_checkpoint(asset.id, original_error)
        if isinstance(original_error, StorageOperationError):
            raise self._translate_storage_error(original_error) from original_error
        raise original_error

    async def _best_effort_mark_checkpoint(
        self, asset_id: UUID, status: str, original_error: BaseException
    ) -> None:
        try:
            await self._mark_checkpoint(asset_id, status)
        except (Exception, asyncio.CancelledError) as tracking_error:
            original_error.recovery_failure = True
            original_error.add_note(
                f"checkpoint status update failed: {type(tracking_error).__name__}"
            )

    async def _best_effort_delete_checkpoint(
        self, asset_id: UUID, original_error: BaseException
    ) -> None:
        try:
            await self._delete_checkpoint(asset_id)
        except (Exception, asyncio.CancelledError) as tracking_error:
            original_error.recovery_failure = True
            original_error.add_note(
                f"checkpoint delete failed: {type(tracking_error).__name__}"
            )

    async def _mark_checkpoint(self, asset_id: UUID, status: str) -> None:
        async with self._session_factory() as session, session.begin():
            asset = await session.get(FileAsset, asset_id, with_for_update=True)
            if asset is not None:
                asset.processing_status = status

    async def _delete_checkpoint(self, asset_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(delete(FileAsset).where(FileAsset.id == asset_id))

    async def _resolve_upload_project(
        self, user_id: UUID, project_id: UUID | None
    ) -> Project:
        async with self._session_factory() as session:
            if project_id is not None:
                project = await self._owned_project(session, user_id, project_id)
                if project.is_archived:
                    raise AssetOperationError(
                        "project_archived", "归档项目不能上传资产", 409
                    )
                return project
            project = await session.scalar(
                select(Project).where(
                    Project.user_id == user_id,
                    Project.is_default.is_(True),
                    Project.deleted_at.is_(None),
                )
            )
            if project is not None:
                return project
            project = Project(user_id=user_id, name="默认项目", is_default=True)
            session.add(project)
            try:
                await session.commit()
                return project
            except IntegrityError as exception:
                await session.rollback()
                project = await session.scalar(
                    select(Project).where(
                        Project.user_id == user_id,
                        Project.is_default.is_(True),
                        Project.deleted_at.is_(None),
                    )
                )
                if project is None:
                    raise AssetOperationError(
                        "project_conflict", "默认项目创建发生冲突", 409
                    ) from exception
                return project

    async def _find_idempotent_asset(
        self, user_id: UUID, idempotency_key: str
    ) -> FileAsset | None:
        async with self._session_factory() as session:
            return await session.scalar(
                select(FileAsset).where(
                    FileAsset.user_id == user_id,
                    FileAsset.idempotency_key == idempotency_key,
                    FileAsset.deleted_at.is_(None),
                )
            )

    @staticmethod
    def _ensure_replayable(asset: FileAsset) -> None:
        if asset.processing_status in _INCOMPLETE_UPLOAD_STATUSES:
            raise AssetOperationError(
                "asset_upload_in_progress", "资产上传仍在处理中", 409
            )

    @staticmethod
    async def _owned_project(
        session: AsyncSession,
        user_id: UUID,
        project_id: UUID,
        for_update: bool = False,
    ) -> Project:
        statement = select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
            Project.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        project = await session.scalar(statement)
        if project is None:
            raise AssetOperationError("project_not_found", "项目不存在", 404)
        return project

    @staticmethod
    def _translate_storage_error(
        exception: StorageOperationError,
    ) -> AssetOperationError:
        translated = AssetOperationError(
            exception.error_code, exception.message, exception.status_code
        )
        for note in getattr(exception, "__notes__", ()):
            translated.add_note(note)
        if has_cleanup_failure(exception):
            translated.quarantine_cleanup_failed = True
        if getattr(exception, "recovery_failure", False):
            translated.recovery_failure = True
        return translated
