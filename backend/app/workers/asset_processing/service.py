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
from app.services.file_safety.contracts import (
    FileDescriptor,
    FileSafetyError,
    ProcessingLimits,
    validate_processing_batch,
)
from app.services.file_safety.output_store import ParsedOutputStore
from app.services.file_safety.parser_runtime import parse_in_subprocess
from app.services.file_safety.parsers import SafeDocumentParser
from app.storage.local import LocalStorageAdapter, StorageOperationError


logger = logging.getLogger(__name__)

PERSISTED_PROCESSING_ERROR_CODES = frozenset(
    {
        "archive_bomb_detected",
        "archive_member_invalid",
        "excel_cell_limit_exceeded",
        "excel_sheet_limit_exceeded",
        "file_corrupt",
        "file_encoding_unsupported",
        "file_encrypted",
        "file_integrity_mismatch",
        "file_mime_mismatch",
        "file_parse_failed",
        "file_too_large",
        "file_type_unsupported",
        "file_unavailable",
        "image_corrupt",
        "image_decoded_too_large",
        "image_too_large",
        "malware_scan_failed",
        "malware_scan_unavailable",
        "office_xml_member_too_large",
        "parsed_output_too_large",
        "parsed_output_write_failed",
        "parser_process_failed",
        "parser_structure_limit_exceeded",
        "parser_timeout",
        "pdf_page_limit_exceeded",
        "processing_cancelled",
        "processing_failed",
        "processing_lease_expired",
        "processing_state_conflict",
        "storage_provider_unsupported",
        "unsafe_xml_detected",
        "virus_detected",
    }
)


class AssetProcessingService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: LocalStorageAdapter,
        output_store: ParsedOutputStore,
        scanner,
        parser: SafeDocumentParser,
        limits: ProcessingLimits,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._output_store = output_store
        self._scanner = scanner
        self._parser = parser
        self._limits = limits

    async def process(self, asset_id: UUID) -> bool:
        asset = await self._claim(asset_id)
        if asset is None:
            return False
        output_key: str | None = None
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
            await self._complete(asset.id, output_key, document)
        except FileSafetyError as exception:
            cleanup_failed = await self._cleanup_output(asset, output_key)
            await self._reject(
                asset.id,
                exception.error_code,
                exception.safe_message,
                recovery_output_key=output_key if cleanup_failed else None,
                warnings=("parsed_output_cleanup_failed",) if cleanup_failed else (),
            )
        except asyncio.CancelledError:
            cleanup_failed = await asyncio.shield(
                self._cleanup_output(asset, output_key)
            )
            await asyncio.shield(
                self._reject(
                    asset.id,
                    "processing_cancelled",
                    "文件处理已中止",
                    recovery_output_key=output_key if cleanup_failed else None,
                    warnings=("parsed_output_cleanup_failed",)
                    if cleanup_failed
                    else (),
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
            cleanup_failed = await self._cleanup_output(asset, output_key)
            await self._reject(
                asset.id,
                "processing_failed",
                "文件处理失败",
                recovery_output_key=output_key if cleanup_failed else None,
                warnings=("parsed_output_cleanup_failed",) if cleanup_failed else (),
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

    async def _complete(self, asset_id: UUID, output_key: str, document) -> None:
        async with self._session_factory() as session:
            result = await session.execute(
                update(FileAsset)
                .where(
                    FileAsset.id == asset_id,
                    FileAsset.processing_status == "parsing",
                    FileAsset.parsed_storage_key == output_key,
                )
                .values(
                    processing_status="ready",
                    parsed_storage_key=output_key,
                    parser_name=document.parser_name,
                    parser_version=document.parser_version,
                    processing_warnings=list(document.warnings),
                    processing_error_code=None,
                    processing_error_message=None,
                    processed_at=utc_now(),
                )
            )
            await session.commit()
            if result.rowcount != 1:
                raise FileSafetyError(
                    "processing_state_conflict", "资产处理状态发生冲突"
                )

    async def _reject(
        self,
        asset_id: UUID,
        error_code: str,
        message: str,
        *,
        recovery_output_key: str | None = None,
        warnings: tuple[str, ...] = (),
    ) -> None:
        if error_code not in PERSISTED_PROCESSING_ERROR_CODES:
            logger.error(
                "unknown_processing_error_code",
                extra={"error_code": error_code[:64]},
            )
            error_code = "processing_failed"
            message = "文件处理失败"
        async with self._session_factory() as session:
            await session.execute(
                update(FileAsset)
                .where(
                    FileAsset.id == asset_id,
                    FileAsset.processing_status.in_(("scanning", "parsing")),
                )
                .values(
                    processing_status="rejected",
                    parsed_storage_key=recovery_output_key,
                    processing_warnings=list(warnings),
                    processing_error_code=error_code[:64],
                    processing_error_message=message[:255],
                    processed_at=utc_now(),
                )
            )
            await session.commit()

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
