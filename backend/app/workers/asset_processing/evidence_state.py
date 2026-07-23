import asyncio
from datetime import timedelta
import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.base import utc_now
from app.models.file_assets import FileAsset
from app.services.evidence.contracts import EvidenceProcessingError
from app.services.evidence.store import EvidenceManifestStore
from app.services.file_safety.contracts import FileSafetyError
from app.workers.asset_processing.processing_contracts import (
    PERSISTED_PROCESSING_ERROR_CODES,
)


logger = logging.getLogger(__name__)


class AssetEvidenceState:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        manifest_store: EvidenceManifestStore,
        *,
        ocr_retry_limit: int,
        ocr_retry_backoff_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._manifest_store = manifest_store
        self._ocr_retry_limit = ocr_retry_limit
        self._ocr_retry_backoff_seconds = ocr_retry_backoff_seconds

    async def transition(
        self, asset_id: UUID, output_key: str, manifest_key: str
    ) -> None:
        async with self._session_factory() as session:
            result = await session.execute(
                update(FileAsset)
                .where(
                    FileAsset.id == asset_id,
                    FileAsset.processing_status == "parsing",
                    FileAsset.parsed_storage_key == output_key,
                )
                .values(manifest_key=manifest_key, manifest_status="building")
            )
            await session.commit()
            if result.rowcount != 1:
                raise EvidenceProcessingError(
                    "evidence_manifest_state_conflict",
                    "Evidence Manifest 状态发生冲突",
                )

    async def complete(
        self,
        asset_id: UUID,
        output_key: str,
        document,
        *,
        manifest,
        stored_manifest,
    ) -> None:
        async with self._session_factory() as session:
            result = await session.execute(
                update(FileAsset)
                .where(
                    FileAsset.id == asset_id,
                    FileAsset.processing_status == "parsing",
                    FileAsset.parsed_storage_key == output_key,
                    FileAsset.manifest_key == stored_manifest.storage_key,
                    FileAsset.manifest_status == "building",
                )
                .values(
                    processing_status="ready",
                    parsed_storage_key=output_key,
                    parser_name=document.parser_name,
                    parser_version=document.parser_version,
                    processing_warnings=sorted(
                        {
                            *document.warnings,
                            *(issue.code for issue in manifest.warnings),
                            *(issue.code for issue in manifest.blockers),
                        }
                    ),
                    processing_error_code=None,
                    processing_error_message=None,
                    manifest_status="valid",
                    manifest_sha256=stored_manifest.sha256,
                    manifest_schema_version=manifest.schema_version,
                    evidence_engine_version=manifest.generator.version,
                    evidence_warning_count=len(manifest.warnings),
                    evidence_blocker_count=len(manifest.blockers),
                    evidence_generated_at=manifest.generated_at,
                    processing_retry_count=0,
                    processing_retry_after=None,
                    processed_at=utc_now(),
                )
            )
            await session.commit()
            if result.rowcount != 1:
                raise FileSafetyError(
                    "processing_state_conflict", "资产处理状态发生冲突"
                )

    async def retry_ocr(self, asset_id: UUID, error_code: str, message: str) -> None:
        async with self._session_factory() as session:
            asset = await session.scalar(
                select(FileAsset).where(FileAsset.id == asset_id).with_for_update()
            )
            if asset is None or asset.processing_status != "parsing":
                raise FileSafetyError(
                    "processing_state_conflict", "资产处理状态发生冲突"
                )
            next_attempt = asset.processing_retry_count + 1
            if next_attempt >= self._ocr_retry_limit:
                asset.processing_status = "rejected"
                asset.manifest_status = "invalid"
                asset.processing_error_code = "ocr_retry_exhausted"
                asset.processing_error_message = "OCR 服务重试次数已耗尽"
                asset.processing_retry_count = next_attempt
                asset.processing_retry_after = None
                asset.processed_at = utc_now()
            else:
                backoff = self._ocr_retry_backoff_seconds * (2 ** (next_attempt - 1))
                asset.processing_status = "quarantined"
                asset.parsed_storage_key = None
                asset.manifest_key = None
                asset.manifest_status = "retryable_error"
                asset.manifest_sha256 = None
                asset.manifest_schema_version = None
                asset.evidence_engine_version = None
                asset.evidence_warning_count = None
                asset.evidence_blocker_count = None
                asset.evidence_generated_at = None
                asset.processing_error_code = error_code[:64]
                asset.processing_error_message = message[:255]
                asset.processing_retry_count = next_attempt
                asset.processing_retry_after = utc_now() + timedelta(seconds=backoff)
                asset.processing_started_at = None
                asset.processed_at = None
            await session.commit()

    async def reject(
        self,
        asset_id: UUID,
        error_code: str,
        message: str,
        *,
        recovery_output_key: str | None = None,
        recovery_manifest_key: str | None = None,
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
                    manifest_key=recovery_manifest_key,
                    manifest_status="invalid",
                    manifest_sha256=None,
                    manifest_schema_version=None,
                    evidence_engine_version=None,
                    evidence_warning_count=None,
                    evidence_blocker_count=None,
                    evidence_generated_at=None,
                    processing_retry_after=None,
                    processing_warnings=list(warnings),
                    processing_error_code=error_code[:64],
                    processing_error_message=message[:255],
                    processed_at=utc_now(),
                )
            )
            await session.commit()

    async def cleanup_manifest(
        self, asset: FileAsset, manifest_key: str | None
    ) -> bool:
        if manifest_key is None:
            return False
        try:
            await asyncio.to_thread(
                self._manifest_store.delete, asset.user_id, asset.id, manifest_key
            )
        except EvidenceProcessingError:
            logger.error(
                "evidence_manifest_cleanup_failed",
                extra={"asset_id": str(asset.id)},
            )
            return True
        return False


def cleanup_warnings(
    output_cleanup_failed: bool, manifest_cleanup_failed: bool
) -> tuple[str, ...]:
    warnings = []
    if output_cleanup_failed:
        warnings.append("parsed_output_cleanup_failed")
    if manifest_cleanup_failed:
        warnings.append("evidence_manifest_cleanup_failed")
    return tuple(warnings)
