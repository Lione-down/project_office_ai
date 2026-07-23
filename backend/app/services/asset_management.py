from collections.abc import AsyncIterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.audit_logs import AuditLog
from app.models.base import utc_now
from app.models.file_assets import FileAsset
from app.models.projects import Project
from app.services.asset_contracts import (
    AssetAuditContext,
    AssetContent,
    AssetOperationError,
    AssetSummary,
    ProjectSummary,
    asset_summary,
    project_summary,
)
from app.services.asset_uploads import AssetUploadService
from app.services.auth_sessions import AuthSessionService, CurrentUser
from app.services.evidence.contracts import EvidenceProcessingError
from app.services.evidence.store import EvidenceManifestStore
from app.services.file_safety.contracts import FileSafetyError
from app.services.file_safety.output_store import ParsedOutputStore
from app.storage.local import LocalStorageAdapter, StorageOperationError


class AssetManagementService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
        storage: LocalStorageAdapter,
        *,
        max_file_bytes: int,
        max_image_bytes: int,
        parsed_outputs: ParsedOutputStore | None = None,
        evidence_manifests: EvidenceManifestStore | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions
        self._storage = storage
        self._max_file_bytes = max_file_bytes
        self._max_image_bytes = max_image_bytes
        self._parsed_outputs = parsed_outputs
        self._evidence_manifests = evidence_manifests
        self._uploads = AssetUploadService(
            session_factory,
            storage,
            max_file_bytes=max_file_bytes,
            max_image_bytes=max_image_bytes,
        )

    async def create_project(self, access_token: str, name: str) -> ProjectSummary:
        user = await self._sessions.authenticate_access(access_token)
        normalized_name = name.strip()
        if not normalized_name:
            raise AssetOperationError("project_name_invalid", "项目名称不能为空", 422)
        project = Project(user_id=user.user_id, name=normalized_name)
        async with self._session_factory() as session, session.begin():
            session.add(project)
        return project_summary(project)

    async def list_projects(self, access_token: str) -> list[ProjectSummary]:
        user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            projects = (
                await session.scalars(
                    select(Project)
                    .where(
                        Project.user_id == user.user_id, Project.deleted_at.is_(None)
                    )
                    .order_by(Project.created_at, Project.id)
                )
            ).all()
        return [project_summary(project) for project in projects]

    async def update_project(
        self, access_token: str, project_id: UUID, changes: dict
    ) -> ProjectSummary:
        user = await self._sessions.authenticate_access(access_token)
        allowed = {"name", "is_archived"}
        if set(changes) - allowed:
            raise AssetOperationError("project_update_invalid", "项目更新字段无效", 422)
        if any(value is None for value in changes.values()):
            raise AssetOperationError("project_update_invalid", "项目更新字段无效", 422)
        if "name" in changes:
            changes["name"] = changes["name"].strip()
            if not changes["name"]:
                raise AssetOperationError(
                    "project_name_invalid", "项目名称不能为空", 422
                )
        async with self._session_factory() as session, session.begin():
            project = await self._owned_project(session, user.user_id, project_id, True)
            for field_name, value in changes.items():
                setattr(project, field_name, value)
        return project_summary(project)

    async def delete_project(self, access_token: str, project_id: UUID) -> None:
        user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session, session.begin():
            project = await self._owned_project(session, user.user_id, project_id, True)
            active_asset_id = await session.scalar(
                select(FileAsset.id).where(
                    FileAsset.user_id == user.user_id,
                    FileAsset.project_id == project.id,
                    FileAsset.deleted_at.is_(None),
                )
            )
            if active_asset_id is not None:
                raise AssetOperationError(
                    "project_not_empty", "项目仍包含活动资产", 409
                )
            project.deleted_at = utc_now()

    async def upload_asset(
        self,
        *,
        access_token: str,
        project_id: UUID | None,
        filename: str,
        content_type: str,
        content: AsyncIterable[bytes],
        idempotency_key: str,
    ) -> AssetSummary:
        user = await self._sessions.authenticate_access(access_token)
        return await self._uploads.upload(
            user_id=user.user_id,
            project_id=project_id,
            filename=filename,
            content_type=content_type,
            content=content,
            idempotency_key=idempotency_key,
        )

    async def find_upload_replay(
        self, access_token: str, idempotency_key: str
    ) -> AssetSummary | None:
        user = await self._sessions.authenticate_access(access_token)
        return await self._uploads.find_replay(user.user_id, idempotency_key)

    async def list_assets(
        self, access_token: str, project_id: UUID | None = None
    ) -> list[AssetSummary]:
        user = await self._sessions.authenticate_access(access_token)
        conditions = [
            FileAsset.user_id == user.user_id,
            FileAsset.deleted_at.is_(None),
        ]
        if project_id is not None:
            conditions.append(FileAsset.project_id == project_id)
        async with self._session_factory() as session:
            assets = (
                await session.scalars(
                    select(FileAsset)
                    .where(*conditions)
                    .order_by(FileAsset.created_at, FileAsset.id)
                )
            ).all()
        return [asset_summary(asset) for asset in assets]

    async def get_asset(self, access_token: str, asset_id: UUID) -> AssetSummary:
        user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            asset = await self._owned_asset(session, user.user_id, asset_id)
        return asset_summary(asset)

    async def open_asset(self, access_token: str, asset_id: UUID) -> AssetContent:
        user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            asset = await self._owned_asset(session, user.user_id, asset_id)
        return self._asset_content(asset)

    async def admin_open_asset(
        self,
        *,
        access_token: str,
        asset_id: UUID,
        reason: str,
        audit: AssetAuditContext,
    ) -> AssetContent:
        admin = await self._sessions.authenticate_access(access_token)
        if admin.role != "admin":
            raise AssetOperationError("admin_required", "需要管理员权限", 403)
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise AssetOperationError("reason_required", "敏感操作必须填写原因", 422)
        async with self._session_factory() as session:
            asset = await session.scalar(
                select(FileAsset).where(
                    FileAsset.id == asset_id, FileAsset.deleted_at.is_(None)
                )
            )
        if asset is None:
            await self._write_admin_audit(
                admin, asset_id, normalized_reason, "failed", audit, None
            )
            raise AssetOperationError("asset_not_found", "资产不存在", 404)
        try:
            content = self._asset_content(asset)
        except AssetOperationError:
            await self._write_admin_audit(
                admin, asset_id, normalized_reason, "failed", audit, asset.user_id
            )
            raise
        await self._write_admin_audit(
            admin, asset_id, normalized_reason, "success", audit, asset.user_id
        )
        return content

    async def delete_asset(self, access_token: str, asset_id: UUID) -> None:
        user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session, session.begin():
            asset = await self._owned_asset(session, user.user_id, asset_id, True)
            reference_id = await session.scalar(
                select(FileAsset.id).where(
                    FileAsset.parent_asset_id == asset.id,
                    FileAsset.deleted_at.is_(None),
                )
            )
            if reference_id is not None:
                raise AssetOperationError("asset_in_use", "资产仍被其他版本引用", 409)
            if asset.processing_status in {"scanning", "parsing"}:
                raise AssetOperationError(
                    "asset_processing_in_progress", "资产仍在处理中", 409
                )
            asset.processing_status = "deleting"
            storage_key = asset.storage_key
            parsed_storage_key = asset.parsed_storage_key
            manifest_key = asset.manifest_key

        try:
            self._storage.delete_asset(user.user_id, asset_id, storage_key)
            if parsed_storage_key is not None:
                if self._parsed_outputs is None:
                    raise FileSafetyError(
                        "parsed_output_store_unavailable",
                        "解析结果存储不可用",
                    )
                self._parsed_outputs.delete(user.user_id, asset_id, parsed_storage_key)
            if manifest_key is not None:
                if self._evidence_manifests is None:
                    raise EvidenceProcessingError(
                        "evidence_manifest_store_unavailable",
                        "Evidence Manifest 存储不可用",
                    )
                self._evidence_manifests.delete(user.user_id, asset_id, manifest_key)
        except StorageOperationError as exception:
            raise self._translate_storage_error(exception) from exception
        except (FileSafetyError, EvidenceProcessingError) as exception:
            raise AssetOperationError(
                "asset_delete_failed", "资产派生文件删除失败", 500
            ) from exception

        async with self._session_factory() as session, session.begin():
            asset = await session.get(FileAsset, asset_id, with_for_update=True)
            if asset is not None and asset.user_id == user.user_id:
                asset.processing_status = "deleted"
                asset.deleted_at = utc_now()

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
    async def _owned_asset(
        session: AsyncSession,
        user_id: UUID,
        asset_id: UUID,
        for_update: bool = False,
    ) -> FileAsset:
        statement = select(FileAsset).where(
            FileAsset.id == asset_id,
            FileAsset.user_id == user_id,
            FileAsset.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        asset = await session.scalar(statement)
        if asset is None:
            raise AssetOperationError("asset_not_found", "资产不存在", 404)
        return asset

    def _asset_content(self, asset: FileAsset) -> AssetContent:
        try:
            path = self._storage.resolve_asset_key(
                asset.user_id, asset.id, asset.storage_key
            )
        except StorageOperationError as exception:
            raise self._translate_storage_error(exception) from exception
        if not path.is_file():
            raise AssetOperationError("asset_content_missing", "资产文件不存在", 404)
        return AssetContent(asset.id, path, asset.original_filename, asset.mime_type)

    async def _write_admin_audit(
        self,
        admin: CurrentUser,
        asset_id: UUID,
        reason: str,
        result: str,
        audit: AssetAuditContext,
        owner_user_id: UUID | None,
    ) -> None:
        entry = AuditLog(
            actor_user_id=admin.user_id,
            action="asset.admin_read",
            target_type="file_asset",
            target_id=asset_id,
            ip_address=audit.ip_address,
            user_agent=audit.user_agent[:255] if audit.user_agent else None,
            reason=reason,
            result=result,
            context={"owner_user_id": str(owner_user_id) if owner_user_id else None},
            trace_id=audit.trace_id,
        )
        async with self._session_factory() as session, session.begin():
            session.add(entry)

    @staticmethod
    def _translate_storage_error(
        exception: StorageOperationError | AssetOperationError,
    ) -> AssetOperationError:
        if isinstance(exception, AssetOperationError):
            return exception
        return AssetOperationError(
            exception.error_code, exception.message, exception.status_code
        )


__all__ = [
    "AssetAuditContext",
    "AssetManagementService",
    "AssetOperationError",
]
