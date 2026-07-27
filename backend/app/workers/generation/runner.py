import asyncio
import logging
from pathlib import Path

from app.core.database import DatabaseManager
from app.core.logging import configure_logging
from app.core.redis import RedisManager
from app.services.credential_limits import (
    CredentialUsageLimiter,
    RedisCredentialBudgetStore,
)
from app.services.generation_combined import CombinedGenerationExecutor
from app.services.generation_runtime import (
    PresentationGenerationPipeline,
    SpreadsheetGenerationPipeline,
)
from app.services.generation_worker import GenerationWorkerService
from app.services.quality.presentation.artifact_store import (
    PresentationQualityArtifactStore,
)
from app.services.quality.presentation.inspector import PresentationPackageInspector
from app.services.quality.presentation.libreoffice import LibreOfficeClient
from app.services.quality.presentation.repair import PresentationDeterministicRepair
from app.services.quality.presentation.service import PresentationQualityService
from app.services.quality.spreadsheet.artifact_store import (
    SpreadsheetQualityArtifactStore,
)
from app.services.quality.spreadsheet.service import SpreadsheetQualityService
from app.services.renderers.excel.output_store import ExcelOutputStore
from app.services.renderers.excel.renderer import ExcelRenderer
from app.services.renderers.excel.service import ExcelOutputService
from app.services.renderers.excel.sidecar import SpreadsheetLibreOfficeClient
from app.services.renderers.presentation.client import PresentationRendererClient
from app.services.renderers.presentation.output_store import PresentationOutputStore
from app.services.renderers.presentation.service import PresentationOutputService
from app.settings.config import Settings, get_settings
from app.storage.local import LocalStorageAdapter
from app.workers.generation.consumer import (
    GenerationQueueConsumer,
    RedisGenerationQueue,
)


logger = logging.getLogger(__name__)


def build_executor(settings: Settings, database: DatabaseManager):
    files_root = settings.files_root
    presentation_output = PresentationOutputService(
        database.session_factory,
        PresentationRendererClient(
            settings.ppt_renderer_url,
            settings.rendered_root,
            timeout_seconds=settings.ppt_renderer_timeout_seconds,
            max_request_bytes=settings.max_presentation_request_bytes,
        ),
        PresentationOutputStore(files_root),
    )
    presentation_quality = PresentationQualityService(
        database.session_factory,
        LocalStorageAdapter(files_root),
        PresentationQualityArtifactStore(files_root),
        PresentationPackageInspector(),
        PresentationDeterministicRepair(),
        LibreOfficeClient(
            settings.libreoffice_url,
            settings.rendered_root,
            timeout_seconds=settings.libreoffice_timeout_seconds,
        ),
        temp_root=Path("/tmp/office-ai-presentation-quality"),
    )
    spreadsheet_output = ExcelOutputService(
        database.session_factory,
        ExcelRenderer(),
        ExcelOutputStore(files_root),
    )
    spreadsheet_quality = SpreadsheetQualityService(
        database.session_factory,
        SpreadsheetLibreOfficeClient(
            settings.libreoffice_url,
            settings.rendered_root,
            timeout_seconds=settings.libreoffice_timeout_seconds,
        ),
        SpreadsheetQualityArtifactStore(files_root),
    )
    return CombinedGenerationExecutor(
        presentation_pipeline=PresentationGenerationPipeline(
            database.session_factory,
            presentation_output,
            presentation_quality,
        ),
        spreadsheet_pipeline=SpreadsheetGenerationPipeline(
            database.session_factory,
            spreadsheet_output,
            spreadsheet_quality,
        ),
    )


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    database = DatabaseManager(settings.database_url)
    redis = RedisManager(settings.redis_url)
    consumer = GenerationQueueConsumer(
        RedisGenerationQueue(redis),
        GenerationWorkerService(
            database.session_factory,
            CredentialUsageLimiter(RedisCredentialBudgetStore(redis)),
        ),
        build_executor(settings, database),
    )
    try:
        while True:
            try:
                await consumer.consume_once()
            except Exception as exception:
                logger.error(
                    "generation_task_consume_failed",
                    extra={"error_type": type(exception).__name__},
                )
                await asyncio.sleep(1)
    finally:
        await redis.close()
        await database.close()


def main() -> None:
    asyncio.run(run())
