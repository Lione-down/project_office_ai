import asyncio
import logging

from app.core.database import DatabaseManager
from app.core.logging import configure_logging
from app.core.redis import RedisManager
from app.services.briefs.service import BriefGenerationService
from app.services.evidence.store import EvidenceManifestStore
from app.services.provider_security import CredentialCipher
from app.services.workflow_worker import WorkflowTaskWorkerService
from app.settings.config import get_settings
from app.workers.workflow.consumer import RedisWorkflowQueue, WorkflowQueueConsumer


logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.master_key is None:
        raise RuntimeError("workflow worker master key is not configured")
    database = DatabaseManager(settings.database_url)
    redis = RedisManager(settings.redis_url)
    brief_generator = BriefGenerationService(
        database.session_factory,
        None,
        EvidenceManifestStore(
            settings.evidence_root,
            max_output_bytes=settings.max_evidence_manifest_bytes,
        ),
        CredentialCipher(settings.master_key),
    )
    consumer = WorkflowQueueConsumer(
        RedisWorkflowQueue(redis),
        WorkflowTaskWorkerService(
            database.session_factory,
            brief_generator,
        ),
    )
    try:
        while True:
            try:
                await consumer.consume_once()
            except Exception as exception:
                logger.error(
                    "workflow_task_consume_failed",
                    extra={"error_type": type(exception).__name__},
                )
                await asyncio.sleep(1)
    finally:
        await redis.close()
        await database.close()


def main() -> None:
    asyncio.run(run())
