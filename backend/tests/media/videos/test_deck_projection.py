from sqlalchemy import select

from app.models.deck_draft_revisions import DeckDraftRevision
from app.models.deck_drafts import DeckDraft
from app.models.media_jobs import MediaJob
from app.services.decks.handoff import DeckHandoffService
from app.services.media.snapshot import build_media_job_snapshot
from tests.media.images.conftest import DRAFT_ID, REVISION_ID, SLIDE_IDS
from tests.media.videos.test_service_worker import command, video_runtime


async def test_deck_media_projection_preserves_video_kind_and_fallback(
    image_harness,
) -> None:
    service, _worker, _adapter = await video_runtime(image_harness)
    created = await service.create(
        "access",
        DRAFT_ID,
        command(),
        "video-deck-projection-0001",
    )
    async with image_harness.session_factory() as session:
        job = await session.scalar(
            select(MediaJob).where(MediaJob.id == created.media_job_id)
        )
        projection = await build_media_job_snapshot(session, job)

    assert projection["kind"] == "video"
    assert projection["fallback_mode"] == "poster_and_attachment"
    assert projection["embedding_enabled"] is False


async def test_deck_handoff_freezes_video_poster_and_independent_attachment(
    image_harness,
) -> None:
    service, worker, adapter = await video_runtime(image_harness)
    created = await service.create(
        "access",
        DRAFT_ID,
        command(),
        "video-deck-handoff-0001",
    )
    await worker.process(created.media_job_id)
    adapter.poll_result = adapter.poll_result.__class__(
        provider_request_id="request-poll-completed",
        video_id="video-opaque-1",
        task_id="task-opaque-1",
        status="completed",
        progress=100,
        seconds=1.0,
        width=320,
        height=180,
        result_url=(
            "https://platform-outputs.agnes-ai.space/videos/"
            "agnes-video-v2.0/task-opaque-1.mp4"
        ),
        retry_after_seconds=None,
        status_summary=200,
    )
    await worker.process(created.media_job_id)

    async with image_harness.session_factory() as session:
        draft = await session.get(DeckDraft, DRAFT_ID)
        revision = await session.get(DeckDraftRevision, REVISION_ID)
        inputs = await DeckHandoffService._media_inputs(session, draft, revision)

    assert [item["input_type"] for item in inputs] == [
        "media_image",
        "media_video_attachment",
    ]
    poster, video = inputs
    assert poster["reference_key"] == str(SLIDE_IDS[1])
    assert poster["snapshot"]["source_kind"] == "video_poster"
    assert poster["snapshot"]["media_role"] == "poster"
    assert video["reference_key"] == str(SLIDE_IDS[1])
    assert video["snapshot"]["media_role"] == "video"
    assert video["snapshot"]["embedding_enabled"] is False
    assert video["snapshot"]["fallback_mode"] == "poster_and_attachment"
