import asyncio
import logging

from app.core.database import DatabaseManager
from app.core.logging import configure_logging
from app.core.redis import RedisManager
from app.services.briefs.service import BriefGenerationService
from app.services.evidence.store import EvidenceManifestStore
from app.services.provider_security import CredentialCipher
from app.services.media.images.worker import ImageJobWorkerService
from app.services.media.videos.worker import VideoJobWorkerService
from app.services.workflow_worker import WorkflowTaskWorkerService
from app.settings.config import get_settings
from app.storage.local import LocalStorageAdapter
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
    credential_cipher = CredentialCipher(settings.master_key)
    consumer = WorkflowQueueConsumer(
        RedisWorkflowQueue(redis),
        WorkflowTaskWorkerService(
            database.session_factory,
            brief_generator,
        ),
        ImageJobWorkerService(
            database.session_factory,
            credential_cipher,
            LocalStorageAdapter(settings.files_root),
            max_image_bytes=settings.max_image_bytes,
            max_decoded_bytes=settings.max_image_decoded_bytes,
            provider_timeout_seconds=settings.image_provider_timeout_seconds,
        ),
        VideoJobWorkerService(
            database.session_factory,
            credential_cipher,
            LocalStorageAdapter(settings.files_root),
            max_video_bytes=settings.video_max_bytes,
            max_duration_seconds=settings.video_max_duration_seconds,
            poll_interval_seconds=settings.video_poll_interval_seconds,
            job_timeout_seconds=settings.video_job_timeout_seconds,
            output_host_allowlist=settings.video_output_hosts,
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
