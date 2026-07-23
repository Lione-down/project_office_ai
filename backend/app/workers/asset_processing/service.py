import asyncio
from datetime import timedelta
from hashlib import sha256
import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.base import utc_now
from app.models.file_assets import FileAsset
from app.services.evidence.contracts import EvidenceProcessingError
from app.services.evidence.store import EvidenceManifestStore
from app.services.file_safety.contracts import (
    FileDescriptor,
    FileSafetyError,
    ProcessingLimits,
    validate_processing_batch,
)
from app.services.file_safety.output_store import ParsedOutputStore
from app.services.file_safety.parser_runtime import parse_in_subprocess
from app.services.file_safety.parsers import SafeDocumentParser
from app.services.ocr.contracts import OcrServiceError
from app.storage.local import LocalStorageAdapter, StorageOperationError
from app.workers.asset_processing.evidence_state import (
    AssetEvidenceState,
    cleanup_warnings,
)


logger = logging.getLogger(__name__)


class AssetProcessingService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: LocalStorageAdapter,
        output_store: ParsedOutputStore,
        scanner,
        parser: SafeDocumentParser,
        limits: ProcessingLimits,
        *,
        evidence_builder,
        manifest_store: EvidenceManifestStore,
        ocr_retry_limit: int,
        ocr_retry_backoff_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._output_store = output_store
        self._scanner = scanner
        self._parser = parser
        self._limits = limits
        self._evidence_builder = evidence_builder
        self._manifest_store = manifest_store
        self._evidence_state = AssetEvidenceState(
            session_factory,
            manifest_store,
            ocr_retry_limit=ocr_retry_limit,
            ocr_retry_backoff_seconds=ocr_retry_backoff_seconds,
        )

    async def process(self, asset_id: UUID) -> bool:
        asset = await self._claim(asset_id)
        if asset is None:
            return False
        output_key: str | None = None
        manifest_key: str | None = None
        try:
            descriptor = self._descriptor(asset)
            self._verify_integrity(asset, descriptor.path)
            await self._scanner.scan(descriptor.path)
            output_key = self._output_store.build_key(asset.user_id, asset.id)
            await self._transition_to_parsing(asset.id, output_key)
            document = await asyncio.to_thread(
                parse_in_subprocess,
                self._parser,
                descriptor,
                timeout_seconds=self._limits.parser_timeout_seconds,
            )
            written_key = await asyncio.to_thread(
                self._output_store.write, asset.user_id, asset.id, document
            )
            if written_key != output_key:
                raise FileSafetyError(
                    "processing_state_conflict", "解析结果存储状态发生冲突"
                )
            manifest_key = self._manifest_store.build_key(asset.user_id, asset.id)
            await self._transition_to_evidence(asset.id, output_key, manifest_key)
            manifest = await self._evidence_builder.build(
                asset_id=asset.id,
                asset_version=f"sha256:{asset.sha256}",
                document=document,
                source_path=descriptor.path,
                mime_type=asset.mime_type,
                content_sha256=asset.sha256,
            )
            stored_manifest = await asyncio.to_thread(
                self._manifest_store.write,
                asset.user_id,
                asset.id,
                manifest,
            )
            if stored_manifest.storage_key != manifest_key:
                raise EvidenceProcessingError(
                    "evidence_manifest_state_conflict",
                    "Evidence Manifest 存储状态发生冲突",
                )
            await self._complete(
                asset.id,
                output_key,
                document,
                manifest=manifest,
                stored_manifest=stored_manifest,
            )
        except OcrServiceError as exception:
            (
                output_cleanup_failed,
                manifest_cleanup_failed,
            ) = await self._cleanup_outputs(asset, output_key, manifest_key)
            if (
                exception.retryable
                and not output_cleanup_failed
                and not manifest_cleanup_failed
            ):
                await self._retry_ocr(
                    asset.id, exception.error_code, exception.safe_message
                )
            else:
                await self._reject(
                    asset.id,
                    exception.error_code,
                    exception.safe_message,
                    recovery_output_key=output_key if output_cleanup_failed else None,
                    recovery_manifest_key=(
                        manifest_key if manifest_cleanup_failed else None
                    ),
                    warnings=self._cleanup_warnings(
                        output_cleanup_failed, manifest_cleanup_failed
                    ),
                )
        except EvidenceProcessingError as exception:
            (
                output_cleanup_failed,
                manifest_cleanup_failed,
            ) = await self._cleanup_outputs(asset, output_key, manifest_key)
            await self._reject(
                asset.id,
                exception.error_code,
                exception.safe_message,
                recovery_output_key=output_key if output_cleanup_failed else None,
                recovery_manifest_key=(
                    manifest_key if manifest_cleanup_failed else None
                ),
                warnings=self._cleanup_warnings(
                    output_cleanup_failed, manifest_cleanup_failed
                ),
            )
        except FileSafetyError as exception:
            (
                output_cleanup_failed,
                manifest_cleanup_failed,
            ) = await self._cleanup_outputs(asset, output_key, manifest_key)
            await self._reject(
                asset.id,
                exception.error_code,
                exception.safe_message,
                recovery_output_key=output_key if output_cleanup_failed else None,
                recovery_manifest_key=(
                    manifest_key if manifest_cleanup_failed else None
                ),
                warnings=self._cleanup_warnings(
                    output_cleanup_failed, manifest_cleanup_failed
                ),
            )
        except asyncio.CancelledError:
            output_cleanup_failed, manifest_cleanup_failed = await asyncio.shield(
                self._cleanup_outputs(asset, output_key, manifest_key)
            )
            await asyncio.shield(
                self._reject(
                    asset.id,
                    "processing_cancelled",
                    "文件处理已中止",
                    recovery_output_key=(output_key if output_cleanup_failed else None),
                    recovery_manifest_key=(
                        manifest_key if manifest_cleanup_failed else None
                    ),
                    warnings=self._cleanup_warnings(
                        output_cleanup_failed, manifest_cleanup_failed
                    ),
                )
            )
            raise
        except Exception as exception:
            logger.error(
                "asset_processing_failed",
                extra={
                    "asset_id": str(asset.id),
                    "error_type": type(exception).__name__,
                },
            )
            (
                output_cleanup_failed,
                manifest_cleanup_failed,
            ) = await self._cleanup_outputs(asset, output_key, manifest_key)
            await self._reject(
                asset.id,
                "processing_failed",
                "文件处理失败",
                recovery_output_key=output_key if output_cleanup_failed else None,
                recovery_manifest_key=(
                    manifest_key if manifest_cleanup_failed else None
                ),
                warnings=self._cleanup_warnings(
                    output_cleanup_failed, manifest_cleanup_failed
                ),
            )
        return True

    async def process_next(self) -> bool:
        await self.reconcile_stale_leases()
        async with self._session_factory() as session:
            asset_id = await session.scalar(
                select(FileAsset.id)
                .where(
                    FileAsset.processing_status == "quarantined",
                    FileAsset.deleted_at.is_(None),
                    or_(
                        FileAsset.processing_retry_after.is_(None),
                        FileAsset.processing_retry_after <= utc_now(),
                    ),
                )
                .order_by(FileAsset.created_at, FileAsset.id)
                .limit(1)
            )
        return False if asset_id is None else await self.process(asset_id)

    async def process_batch(self, asset_ids: list[UUID]) -> int:
        if len(asset_ids) > self._limits.max_task_files:
            raise FileSafetyError(
                "task_file_limit_exceeded", "任务文件数量超过允许上限"
            )
        if len(set(asset_ids)) != len(asset_ids):
            raise FileSafetyError("processing_batch_invalid", "处理批次无效")
        async with self._session_factory() as session:
            assets = list(
                await session.scalars(
                    select(FileAsset).where(FileAsset.id.in_(asset_ids))
                )
            )
        by_id = {asset.id: asset for asset in assets}
        if len(by_id) != len(asset_ids):
            raise FileSafetyError("processing_batch_invalid", "处理批次无效")
        ordered_assets = [by_id[asset_id] for asset_id in asset_ids]
        if any(
            asset.processing_status != "quarantined" or asset.deleted_at is not None
            for asset in ordered_assets
        ):
            raise FileSafetyError("processing_batch_invalid", "处理批次无效")
        descriptors = [self._descriptor(asset) for asset in ordered_assets]
        validate_processing_batch(descriptors, self._limits)
        processed_count = 0
        for asset_id in asset_ids:
            if await self.process(asset_id):
                processed_count += 1
        return processed_count

    async def reconcile_stale_leases(self) -> int:
        cutoff = utc_now() - timedelta(seconds=self._limits.processing_lease_seconds)
        async with self._session_factory() as session:
            result = await session.execute(
                update(FileAsset)
                .where(
                    FileAsset.processing_status.in_(("scanning", "parsing")),
                    FileAsset.deleted_at.is_(None),
                    or_(
                        FileAsset.processing_started_at.is_(None),
                        FileAsset.processing_started_at < cutoff,
                    ),
                )
                .values(
                    processing_status="rejected",
                    manifest_status="invalid",
                    processing_error_code="processing_lease_expired",
                    processing_error_message="文件处理租约已过期",
                    processed_at=utc_now(),
                )
            )
            await session.commit()
            return result.rowcount

    async def _claim(self, asset_id: UUID) -> FileAsset | None:
        async with self._session_factory() as session:
            result = await session.execute(
                update(FileAsset)
                .where(
                    FileAsset.id == asset_id,
                    FileAsset.processing_status == "quarantined",
                    FileAsset.deleted_at.is_(None),
                )
                .values(
                    processing_status="scanning",
                    processing_started_at=utc_now(),
                    processed_at=None,
                    parsed_storage_key=None,
                    manifest_key=None,
                    manifest_status=None,
                    manifest_sha256=None,
                    manifest_schema_version=None,
                    evidence_engine_version=None,
                    evidence_warning_count=None,
                    evidence_blocker_count=None,
                    evidence_generated_at=None,
                    processing_retry_after=None,
                    parser_name=None,
                    parser_version=None,
                    processing_warnings=None,
                    processing_error_code=None,
                    processing_error_message=None,
                )
            )
            await session.commit()
            if result.rowcount != 1:
                return None
            return await session.get(FileAsset, asset_id)

    def _descriptor(self, asset: FileAsset) -> FileDescriptor:
        if asset.storage_provider != self._storage.provider:
            raise FileSafetyError("storage_provider_unsupported", "存储类型不受支持")
        try:
            path = self._storage.resolve_asset_key(
                asset.user_id, asset.id, asset.storage_key
            )
        except StorageOperationError as exception:
            raise FileSafetyError("file_unavailable", "文件不可读取") from exception
        return FileDescriptor(
            path=path,
            extension=Path(asset.original_filename).suffix.lower(),
            mime_type=asset.mime_type,
            byte_size=asset.byte_size,
            category=asset.file_category,
        )

    @staticmethod
    def _verify_integrity(asset: FileAsset, path: Path) -> None:
        try:
            digest = sha256()
            byte_size = 0
            with path.open("rb") as file_handle:
                while chunk := file_handle.read(1024 * 1024):
                    byte_size += len(chunk)
                    digest.update(chunk)
        except OSError as exception:
            raise FileSafetyError("file_unavailable", "文件不可读取") from exception
        if byte_size != asset.byte_size or digest.hexdigest() != asset.sha256:
            raise FileSafetyError("file_integrity_mismatch", "隔离文件完整性校验失败")

    async def _transition_to_parsing(
        self, asset_id: UUID, intended_output_key: str
    ) -> None:
        async with self._session_factory() as session:
            result = await session.execute(
                update(FileAsset)
                .where(
                    FileAsset.id == asset_id,
                    FileAsset.processing_status == "scanning",
                )
                .values(
                    processing_status="parsing",
                    parsed_storage_key=intended_output_key,
                )
            )
            await session.commit()
            if result.rowcount != 1:
                raise FileSafetyError(
                    "processing_state_conflict", "资产处理状态发生冲突"
                )

    async def _transition_to_evidence(
        self, asset_id: UUID, output_key: str, manifest_key: str
    ) -> None:
        await self._evidence_state.transition(asset_id, output_key, manifest_key)

    async def _complete(
        self,
        asset_id: UUID,
        output_key: str,
        document,
        *,
        manifest,
        stored_manifest,
    ) -> None:
        await self._evidence_state.complete(
            asset_id,
            output_key,
            document,
            manifest=manifest,
            stored_manifest=stored_manifest,
        )

    async def _retry_ocr(self, asset_id: UUID, error_code: str, message: str) -> None:
        await self._evidence_state.retry_ocr(asset_id, error_code, message)

    async def _reject(
        self,
        asset_id: UUID,
        error_code: str,
        message: str,
        *,
        recovery_output_key: str | None = None,
        recovery_manifest_key: str | None = None,
        warnings: tuple[str, ...] = (),
    ) -> None:
        await self._evidence_state.reject(
            asset_id,
            error_code,
            message,
            recovery_output_key=recovery_output_key,
            recovery_manifest_key=recovery_manifest_key,
            warnings=warnings,
        )

    async def _cleanup_outputs(
        self,
        asset: FileAsset,
        output_key: str | None,
        manifest_key: str | None,
    ) -> tuple[bool, bool]:
        return (
            await self._cleanup_output(asset, output_key),
            await self._cleanup_manifest(asset, manifest_key),
        )

    async def _cleanup_output(self, asset: FileAsset, output_key: str | None) -> bool:
        if output_key is None:
            return False
        try:
            await asyncio.to_thread(
                self._output_store.delete, asset.user_id, asset.id, output_key
            )
        except FileSafetyError:
            logger.error(
                "parsed_output_cleanup_failed",
                extra={"asset_id": str(asset.id)},
            )
            return True
        return False

    async def _cleanup_manifest(
        self, asset: FileAsset, manifest_key: str | None
    ) -> bool:
        return await self._evidence_state.cleanup_manifest(asset, manifest_key)

    @staticmethod
    def _cleanup_warnings(
        output_cleanup_failed: bool, manifest_cleanup_failed: bool
    ) -> tuple[str, ...]:
        return cleanup_warnings(output_cleanup_failed, manifest_cleanup_failed)
