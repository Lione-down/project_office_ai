from sqlalchemy import select

from app.models.credit_ledger import CreditLedger
from app.models.file_assets import FileAsset
from app.models.media_jobs import MediaJob
from app.models.outbox_events import OutboxEvent
from app.models.provider_calls import ProviderCall
from app.models.users import User
from app.models.workflow_tasks import WorkflowTask
from app.providers.agnes import ErrorClassification
from app.services.media.images.contracts import ImageJobCreateCommand
from app.services.media.images.service import ImageJobOperationError

from .conftest import (
    DRAFT_ID,
    MODEL_ID,
    OTHER_USER_ID,
    SLIDE_IDS,
    USER_ID,
)


def command(*, prompt: str = "Synthetic quarterly trend illustration"):
    return ImageJobCreateCommand(
        expected_revision=1,
        slide_id=SLIDE_IDS[1],
        action="generate",
        prompt=prompt,
        alt_text="季度趋势合成插画",
        model_id=MODEL_ID,
        requested_size="2K",
        requested_ratio="16:9",
        crop_mode="cover",
        confirmed=True,
        accepted_estimated_credits=12,
    )


async def test_image_job_create_is_explicit_idempotent_and_reserves_once(
    image_harness,
) -> None:
    created = await image_harness.service.create(
        "access",
        DRAFT_ID,
        command(),
        "image-create-0001",
    )
    replayed = await image_harness.service.create(
        "access",
        DRAFT_ID,
        command(),
        "image-create-0001",
    )

    assert created.status == "queued"
    assert replayed.media_job_id == created.media_job_id
    assert replayed.replayed is True
    async with image_harness.session_factory() as session:
        assert len(list(await session.scalars(select(MediaJob)))) == 1
        assert len(list(await session.scalars(select(WorkflowTask)))) == 1
        assert len(list(await session.scalars(select(OutboxEvent)))) == 1
        ledger = list(await session.scalars(select(CreditLedger)))
        user = await session.get(User, USER_ID)
    assert [(item.entry_type, item.amount) for item in ledger] == [
        ("media_reserve", -12)
    ]
    assert user.credit_balance == 9_988

    try:
        await image_harness.service.create(
            "access",
            DRAFT_ID,
            command(prompt="Different prompt"),
            "image-create-0001",
        )
    except ImageJobOperationError as error:
        assert error.error_code == "idempotency_conflict"
    else:
        raise AssertionError("payload drift must fail closed")


async def test_image_job_create_rejects_disallowed_prompt_before_reserving(
    image_harness,
) -> None:
    try:
        await image_harness.service.create(
            "access",
            DRAFT_ID,
            command(prompt="Create 儿童色情 content"),
            "image-create-policy",
        )
    except ImageJobOperationError as error:
        assert error.error_code == "image_content_policy_rejected"
        assert error.status_code == 422
    else:
        raise AssertionError("disallowed prompt must fail closed")

    async with image_harness.session_factory() as session:
        assert len(list(await session.scalars(select(MediaJob)))) == 0
        assert len(list(await session.scalars(select(CreditLedger)))) == 0


async def test_image_worker_creates_one_owner_ready_asset_and_redacted_call(
    image_harness,
) -> None:
    created = await image_harness.service.create(
        "access",
        DRAFT_ID,
        command(),
        "image-create-0002",
    )
    completed = await image_harness.worker.process(created.media_job_id)
    replayed = await image_harness.worker.process(created.media_job_id)

    assert completed.status == "succeeded"
    assert completed.actual_width == 64
    assert completed.actual_height == 36
    assert replayed.media_job_id == completed.media_job_id
    assert len(image_harness.adapter.requests) == 1
    async with image_harness.session_factory() as session:
        assets = list(await session.scalars(select(FileAsset)))
        calls = list(await session.scalars(select(ProviderCall)))
        ledger = list(
            await session.scalars(
                select(CreditLedger).order_by(CreditLedger.created_at)
            )
        )
    assert len(assets) == 1
    assert assets[0].user_id == USER_ID
    assert assets[0].processing_status == "ready"
    assert assets[0].generated_media_job_id == created.media_job_id
    assert assets[0].media_width == 64
    assert assets[0].media_height == 36
    assert len(calls) == 1
    assert calls[0].is_redacted is True
    assert calls[0].media_job_id == created.media_job_id
    assert [item.entry_type for item in ledger] == [
        "media_reserve",
        "media_finalize",
    ]


async def test_image_job_owner_scope_hides_cross_owner_identity(image_harness) -> None:
    created = await image_harness.service.create(
        "access",
        DRAFT_ID,
        command(),
        "image-create-0003",
    )
    image_harness.sessions.user_id = OTHER_USER_ID

    try:
        await image_harness.service.get("access-other", created.media_job_id)
    except ImageJobOperationError as error:
        assert error.error_code == "media_job_not_found"
        assert error.status_code == 404
    else:
        raise AssertionError("cross-owner job must be hidden")


async def test_provider_uncertain_is_not_retried_or_released_automatically(
    image_harness,
) -> None:
    class UncertainAdapter:
        def __init__(self) -> None:
            self.calls = 0

        async def create_image(self, **_values):
            self.calls += 1
            raise TimeoutError("synthetic timeout")

        @staticmethod
        def classify_error(_exception):
            return ErrorClassification(
                "provider_uncertain",
                retryable=False,
                disable_credential=False,
                uncertain=True,
            )

    adapter = UncertainAdapter()
    image_harness.worker._adapter_factory = lambda _provider: adapter
    created = await image_harness.service.create(
        "access",
        DRAFT_ID,
        command(),
        "image-create-uncertain-0001",
    )

    first = await image_harness.worker.process(created.media_job_id)
    replayed = await image_harness.worker.process(created.media_job_id)

    assert first.status == "provider_uncertain"
    assert replayed.status == "provider_uncertain"
    assert adapter.calls == 1
    async with image_harness.session_factory() as session:
        ledger = list(await session.scalars(select(CreditLedger)))
    assert [item.entry_type for item in ledger] == ["media_reserve"]


async def test_image_storage_failure_creates_no_ready_asset_and_releases_reserve(
    image_harness,
) -> None:
    class FailingStorage:
        @staticmethod
        def write_media_image(**_values):
            raise OSError("synthetic storage failure")

    image_harness.worker._storage = FailingStorage()
    created = await image_harness.service.create(
        "access",
        DRAFT_ID,
        command(),
        "image-storage-failure-0001",
    )

    failed = await image_harness.worker.process(created.media_job_id)

    assert failed.status == "failed"
    assert failed.error_code == "media_storage_failed"
    assert failed.output_asset is None
    async with image_harness.session_factory() as session:
        assets = list(await session.scalars(select(FileAsset)))
        calls = list(await session.scalars(select(ProviderCall)))
        ledger = list(await session.scalars(select(CreditLedger)))
    assert assets == []
    assert calls[0].provider_request_id == "provider-image-1"
    assert [item.entry_type for item in ledger] == [
        "media_reserve",
        "media_release",
    ]


async def test_cancel_after_submission_is_uncertain_in_job_and_workflow(
    image_harness,
) -> None:
    created = await image_harness.service.create(
        "access",
        DRAFT_ID,
        command(),
        "image-cancel-submitted-0001",
    )
    async with image_harness.session_factory() as session, session.begin():
        job = await session.get(MediaJob, created.media_job_id)
        job.status = "submitted"
        job.progress = 10

    cancelled = await image_harness.service.cancel(
        "access",
        created.media_job_id,
    )

    assert cancelled.status == "provider_uncertain"
    async with image_harness.session_factory() as session:
        workflow = await session.get(WorkflowTask, created.workflow_task_id)
        ledger = list(await session.scalars(select(CreditLedger)))
    assert workflow.status == "provider_uncertain"
    assert workflow.failure_code == "provider_uncertain"
    assert [item.entry_type for item in ledger] == ["media_reserve"]
