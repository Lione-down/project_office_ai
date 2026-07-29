from dataclasses import replace
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.ai_models import AiModel
from app.models.credit_ledger import CreditLedger
from app.models.file_assets import FileAsset
from app.models.media_jobs import MediaJob
from app.models.outbox_events import OutboxEvent
from app.models.workflow_tasks import WorkflowTask
from app.providers.agnes import ErrorClassification, ProviderVideo
from app.services.media.videos.contracts import VideoJobCreateCommand
from app.services.media.videos.service import VideoJobOperationError, VideoJobService
from app.services.media.videos.worker import VideoJobWorkerService
from tests.media.images.conftest import DRAFT_ID, MODEL_ID, SLIDE_IDS
from tests.media.videos.test_validation import synthetic_mp4


def command(**overrides) -> VideoJobCreateCommand:
    payload = {
        "expected_revision": 1,
        "slide_id": str(SLIDE_IDS[1]),
        "action": "generate",
        "mode": "text-to-video",
        "prompt": "Synthetic geometric shapes moving across a neutral background",
        "negative_prompt": "logos, watermarks",
        "model_id": str(MODEL_ID),
        "width": 1152,
        "height": 768,
        "num_frames": 81,
        "frame_rate": 24,
        "confirmed": True,
        "accepted_estimated_credits": 0,
        "embed_requested": False,
    }
    payload.update(overrides)
    return VideoJobCreateCommand.model_validate(payload)


class VideoAdapter:
    def __init__(self) -> None:
        self.created: list = []
        self.polled: list = []
        self.poll_result = ProviderVideo(
            provider_request_id="request-poll-1",
            video_id="video-opaque-1",
            task_id="task-opaque-1",
            status="in_progress",
            progress=42,
            seconds=3.375,
            width=1152,
            height=768,
            result_url=None,
            retry_after_seconds=9,
            status_summary=200,
        )
        self.poll_error: Exception | None = None

    async def create_video(self, *, api_key, request):
        assert api_key == "test-only-provider-key"
        self.created.append(request)
        return ProviderVideo(
            provider_request_id="request-create-1",
            video_id="video-opaque-1",
            task_id="task-opaque-1",
            status="queued",
            progress=0,
            seconds=3.375,
            width=1152,
            height=768,
            result_url=None,
            retry_after_seconds=7,
            status_summary=200,
        )

    async def get_video(self, *, api_key, model, video_id, **_kwargs):
        assert api_key == "test-only-provider-key"
        assert model == "agnes-video-v2.0"
        assert video_id == "video-opaque-1"
        self.polled.append(video_id)
        if self.poll_error is not None:
            raise self.poll_error
        return self.poll_result

    def classify_error(self, exception):
        if isinstance(exception, TimeoutError):
            return ErrorClassification("rate_limited", True, False, False)
        raise AssertionError("unexpected error must not classify")


async def video_runtime(image_harness):
    async with image_harness.session_factory() as session, session.begin():
        model = await session.get(AiModel, MODEL_ID, with_for_update=True)
        model.model_code = "agnes-video-v2.0"
        model.display_name = "Agnes Video V2.0"
        model.capabilities = {
            "video_generation": True,
            "video_embedding": False,
            "credit_per_second": 0,
        }
        model.credit_multiplier = Decimal("1.0000")
    service = VideoJobService(
        image_harness.session_factory,
        image_harness.sessions,
        max_active_jobs_per_user=2,
        max_prompt_chars=2000,
        embedding_enabled=False,
    )
    adapter = VideoAdapter()

    async def download(url: str, **_kwargs) -> bytes:
        assert url.startswith("https://platform-outputs.agnes-ai.space/")
        return synthetic_mp4()

    worker = VideoJobWorkerService(
        image_harness.session_factory,
        image_harness.worker._cipher,
        image_harness.storage,
        adapter_factory=lambda _provider: adapter,
        downloader=download,
        max_video_bytes=10 * 1024 * 1024,
        max_duration_seconds=20,
        poll_interval_seconds=5,
        job_timeout_seconds=1800,
        output_host_allowlist=("platform-outputs.agnes-ai.space",),
    )
    return service, worker, adapter


async def test_video_create_is_owner_scoped_idempotent_and_queues_once(
    image_harness,
) -> None:
    service, _worker, _adapter = await video_runtime(image_harness)

    first = await service.create("access", DRAFT_ID, command(), "video-create-0001")
    replay = await service.create("access", DRAFT_ID, command(), "video-create-0001")

    assert first.status == "queued"
    assert first.mode == "text-to-video"
    assert first.embedding_enabled is False
    assert replay.media_job_id == first.media_job_id
    assert replay.replayed is True
    async with image_harness.session_factory() as session:
        events = list(
            await session.scalars(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_id == first.media_job_id
                )
            )
        )
        ledger = list(
            await session.scalars(
                select(CreditLedger).where(
                    CreditLedger.media_job_id == first.media_job_id
                )
            )
        )
        workflow = await session.get(WorkflowTask, first.workflow_task_id)
    assert [event.event_type for event in events] == ["video.generate"]
    assert [entry.entry_type for entry in ledger] == ["media_reserve"]
    assert workflow.resource_kind == "media_video"
    assert workflow.progress == 0

    with pytest.raises(VideoJobOperationError) as conflict:
        await service.create(
            "access",
            DRAFT_ID,
            command(prompt="Different synthetic motion"),
            "video-create-0001",
        )
    assert conflict.value.error_code == "idempotency_conflict"


async def test_video_worker_submits_then_polls_server_authoritative_progress(
    image_harness,
) -> None:
    service, worker, adapter = await video_runtime(image_harness)
    created = await service.create("access", DRAFT_ID, command(), "video-create-0002")

    submitted = await worker.process(created.media_job_id)
    running = await worker.process(created.media_job_id)

    assert submitted.status == "submitted"
    assert submitted.provider_job_id == "video-opaque-1"
    assert running.status == "running"
    assert running.progress == 42
    assert running.next_poll_after_seconds == 9
    assert len(adapter.created) == 1
    assert len(adapter.polled) == 1
    async with image_harness.session_factory() as session:
        events = list(
            await session.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.aggregate_id == created.media_job_id)
                .order_by(OutboxEvent.created_at)
            )
        )
    assert [event.event_type for event in events] == [
        "video.generate",
        "video.poll",
        "video.poll",
    ]


async def test_video_success_persists_immutable_video_and_poster_assets(
    image_harness,
) -> None:
    service, worker, adapter = await video_runtime(image_harness)
    created = await service.create("access", DRAFT_ID, command(), "video-create-0003")
    await worker.process(created.media_job_id)
    adapter.poll_result = replace(
        adapter.poll_result,
        status="completed",
        progress=100,
        width=320,
        height=180,
        seconds=1.0,
        result_url=(
            "https://platform-outputs.agnes-ai.space/videos/"
            "agnes-video-v2.0/task-opaque-1.mp4"
        ),
        retry_after_seconds=None,
    )

    completed = await worker.process(created.media_job_id)

    assert completed.status == "succeeded"
    assert completed.output_video is not None
    assert completed.output_video.container == "mp4"
    assert completed.output_video.codec == "h264"
    assert completed.output_video.download_path.endswith("/download")
    assert completed.poster is not None
    assert completed.poster.preview_path.endswith("/preview")
    assert completed.fallback_mode == "poster_and_attachment"
    assert completed.embedding_enabled is False
    async with image_harness.session_factory() as session:
        assets = list(
            await session.scalars(
                select(FileAsset)
                .where(FileAsset.generated_media_job_id == created.media_job_id)
                .order_by(FileAsset.media_role)
            )
        )
        ledger = list(
            await session.scalars(
                select(CreditLedger)
                .where(CreditLedger.media_job_id == created.media_job_id)
                .order_by(CreditLedger.created_at)
            )
        )
    assert [asset.media_role for asset in assets] == ["poster", "video"]
    assert all(asset.processing_status == "ready" for asset in assets)
    assert [entry.entry_type for entry in ledger] == [
        "media_reserve",
        "media_finalize",
    ]


async def test_video_cancel_after_submit_is_uncertain_without_retry_or_release(
    image_harness,
) -> None:
    service, worker, adapter = await video_runtime(image_harness)
    created = await service.create("access", DRAFT_ID, command(), "video-create-0004")
    await worker.process(created.media_job_id)

    cancelled = await service.cancel("access", created.media_job_id)

    assert cancelled.status == "provider_uncertain"
    assert cancelled.error_code == "provider_uncertain"
    assert adapter.polled == []
    async with image_harness.session_factory() as session:
        job = await session.get(MediaJob, created.media_job_id)
        entries = list(
            await session.scalars(
                select(CreditLedger).where(
                    CreditLedger.media_job_id == created.media_job_id
                )
            )
        )
    assert job.reserved_credits == 0
    assert [entry.entry_type for entry in entries] == ["media_reserve"]


async def test_video_poll_retries_transient_errors_with_a_bounded_outbox_event(
    image_harness,
) -> None:
    service, worker, adapter = await video_runtime(image_harness)
    created = await service.create("access", DRAFT_ID, command(), "video-create-0005")
    await worker.process(created.media_job_id)
    adapter.poll_error = TimeoutError("synthetic transient poll error")

    retrying = await worker.process(created.media_job_id)

    assert retrying.status == "submitted"
    assert retrying.next_poll_after_seconds == 5
    second_retry = await worker.process(created.media_job_id)
    uncertain = await worker.process(created.media_job_id)
    assert second_retry.status == "submitted"
    assert uncertain.status == "provider_uncertain"
    async with image_harness.session_factory() as session:
        events = list(
            await session.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.aggregate_id == created.media_job_id)
                .order_by(OutboxEvent.created_at)
            )
        )
    assert [event.event_type for event in events] == [
        "video.generate",
        "video.poll",
        "video.poll",
        "video.poll",
    ]
