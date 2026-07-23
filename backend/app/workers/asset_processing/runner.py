import asyncio
import logging

from app.core.database import DatabaseManager
from app.core.logging import configure_logging
from app.services.evidence.builder import EvidenceManifestBuilder
from app.services.evidence.store import EvidenceManifestStore
from app.services.file_safety.clamav import ClamAVScanner
from app.services.file_safety.contracts import ProcessingLimits
from app.services.file_safety.output_store import ParsedOutputStore
from app.services.file_safety.parsers import SafeDocumentParser
from app.services.ocr.client import PaddleOcrClient
from app.settings.config import get_settings
from app.storage.local import LocalStorageAdapter
from app.workers.asset_processing.service import AssetProcessingService


logger = logging.getLogger(__name__)


def _limits(settings) -> ProcessingLimits:
    return ProcessingLimits(
        max_file_bytes=settings.max_file_bytes,
        max_image_bytes=settings.max_image_bytes,
        max_image_decoded_bytes=settings.max_image_decoded_bytes,
        max_task_files=settings.max_task_files,
        max_task_bytes=settings.max_task_bytes,
        max_pdf_pages=settings.max_pdf_pages,
        max_excel_sheets=settings.max_excel_sheets,
        max_excel_non_empty_cells=settings.max_excel_non_empty_cells,
        max_archive_entries=settings.max_archive_entries,
        max_archive_uncompressed_bytes=settings.max_archive_uncompressed_bytes,
        max_archive_compression_ratio=settings.max_archive_compression_ratio,
        max_office_xml_member_bytes=settings.max_office_xml_member_bytes,
        max_parser_structural_items=settings.max_parser_structural_items,
        max_output_bytes=settings.max_parsed_output_bytes,
        parser_timeout_seconds=settings.parser_timeout_seconds,
        processing_lease_seconds=settings.processing_lease_seconds,
    )


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    database = DatabaseManager(settings.database_url)
    limits = _limits(settings)
    processor = AssetProcessingService(
        database.session_factory,
        LocalStorageAdapter(settings.files_root),
        ParsedOutputStore(
            settings.parsed_root,
            max_output_bytes=settings.max_parsed_output_bytes,
        ),
        ClamAVScanner(
            settings.clamav_host,
            settings.clamav_port,
            timeout_seconds=settings.clamav_timeout_seconds,
        ),
        SafeDocumentParser(limits),
        limits,
        evidence_builder=EvidenceManifestBuilder(
            PaddleOcrClient(
                settings.paddleocr_url,
                timeout_seconds=settings.ocr_timeout_seconds,
                max_response_bytes=settings.max_ocr_response_bytes,
                max_items=settings.max_ocr_items,
            ),
            max_evidence_items=settings.max_evidence_items,
        ),
        manifest_store=EvidenceManifestStore(
            settings.evidence_root,
            max_output_bytes=settings.max_evidence_manifest_bytes,
        ),
        ocr_retry_limit=settings.ocr_retry_limit,
        ocr_retry_backoff_seconds=settings.ocr_retry_backoff_seconds,
    )
    try:
        while True:
            try:
                processed = await processor.process_next()
            except Exception as exception:
                logger.error(
                    "asset_processing_poll_failed",
                    extra={"error_type": type(exception).__name__},
                )
                processed = False
            if not processed:
                await asyncio.sleep(2)
    finally:
        await database.close()


def main() -> None:
    asyncio.run(run())
