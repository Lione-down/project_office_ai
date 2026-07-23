from uuid import UUID

import pytest
from sqlalchemy import select

from app.models.credit_ledger import CreditLedger
from app.models.file_assets import FileAsset
from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.models.users import User
from app.services.generation_contracts import GenerationOperationError
from app.services.generation_worker import (
    ControlledStepExecutor,
    GenerationWorkerService,
    StepExecutionResult,
)
from tests.generation.conftest import BRIEF_ID, PROJECT_ID, USER_ID


class AllowAllCredentialLimiter:
    async def acquire(self, **_kwargs) -> bool:
        return True


class CheckpointingExecutor:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def execute(self, context):
        async with self._session_factory() as session, session.begin():
            step = await session.get(
                GenerationTaskStep,
                context.step_id,
                with_for_update=True,
            )
            step.checkpoint = {
                **dict(step.checkpoint or {}),
                "output_asset_id": str(PPT_ASSET_ID),
                "asset_version": f"sha256:{'a' * 64}",
                "quality_status": "passed",
                "quality_download_allowed": True,
                "quality_report_schema_version": "presentation-quality-report.v1",
            }
        return StepExecutionResult.succeeded()


class RetryingCheckpointExecutor:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self.calls = 0

    async def execute(self, context):
        self.calls += 1
        async with self._session_factory() as session, session.begin():
            step = await session.get(
                GenerationTaskStep,
                context.step_id,
                with_for_update=True,
            )
            if self.calls == 1:
                step.checkpoint = {
                    **dict(step.checkpoint or {}),
                    "renderer_result": {"sha256": "a" * 64},
                }
                return StepExecutionResult.retryable_failure(
                    "spreadsheet_quality_temporarily_unavailable"
                )
            assert step.checkpoint["renderer_result"] == {"sha256": "a" * 64}
        return StepExecutionResult.succeeded()


PPT_ASSET_ID = UUID("019f6000-0000-7000-8000-000000000031")


async def test_one_success_one_failure_is_partial_and_settlement_replay_is_idempotent(
    generation_harness,
) -> None:
    await generation_harness.set_combined()
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "combined-partial-001"
    )
    worker = GenerationWorkerService(
        generation_harness.session_factory,
        AllowAllCredentialLimiter(),
    )
    processed = await worker.process(
        created.task_id,
        ControlledStepExecutor(
            [
                StepExecutionResult.succeeded(
                    output_asset_id=PPT_ASSET_ID,
                    asset_version=f"sha256:{'a' * 64}",
                    quality_status="passed",
                    download_allowed=True,
                    quality_report_schema_version="presentation-quality-report.v1",
                ),
                StepExecutionResult.permanent_failure(
                    "spreadsheet_quality_blocked",
                    quality_status="blocked",
                    download_allowed=False,
                    quality_report_schema_version="workbook-quality-report.v1",
                ),
            ]
        ),
    )
    replayed = await worker.process(
        created.task_id,
        ControlledStepExecutor([]),
    )

    async with generation_harness.session_factory() as session:
        user = await session.get(User, USER_ID)
        entries = list(
            await session.scalars(
                select(CreditLedger).where(CreditLedger.task_id == created.task_id)
            )
        )

    assert processed.status == replayed.status == "partial_success"
    assert processed.settled_credits == 800
    assert processed.steps[0].output_asset_id == PPT_ASSET_ID
    assert processed.steps[0].quality_status == "passed"
    assert processed.steps[0].download_allowed is True
    assert processed.steps[1].quality_status == "blocked"
    assert processed.steps[1].download_allowed is False
    assert user.credit_balance == 4_200
    assert [(entry.entry_type, entry.amount) for entry in entries] == [
        ("generation_reserve", -1600),
        ("generation_finalize", 0),
        ("generation_release", 800),
    ]


async def test_two_quality_passes_complete_combined_task(
    generation_harness,
) -> None:
    await generation_harness.set_combined()
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "combined-success-001"
    )
    outcomes = [
        StepExecutionResult.succeeded(
            output_asset_id=UUID("019f6000-0000-7000-8000-000000000032"),
            asset_version=f"sha256:{'b' * 64}",
            quality_status="passed",
            download_allowed=True,
            quality_report_schema_version="presentation-quality-report.v1",
        ),
        StepExecutionResult.succeeded(
            output_asset_id=UUID("019f6000-0000-7000-8000-000000000033"),
            asset_version=f"sha256:{'c' * 64}",
            quality_status="passed_with_warnings",
            download_allowed=True,
            quality_report_schema_version="workbook-quality-report.v1",
        ),
    ]

    processed = await GenerationWorkerService(
        generation_harness.session_factory,
        AllowAllCredentialLimiter(),
    ).process(created.task_id, ControlledStepExecutor(outcomes))

    assert processed.status == "succeeded"
    assert processed.settled_credits == 1600
    assert {step.output_kind for step in processed.steps} == {"pptx", "xlsx"}
    assert all(step.download_allowed for step in processed.steps)


def test_quality_outcome_rejects_contradictory_success_and_download_state() -> None:
    with pytest.raises(ValueError, match="quality outcome is inconsistent"):
        StepExecutionResult.succeeded(
            output_asset_id=PPT_ASSET_ID,
            asset_version=f"sha256:{'a' * 64}",
            quality_status="blocked",
            download_allowed=True,
            quality_report_schema_version="workbook-quality-report.v1",
        )

    with pytest.raises(ValueError, match="quality outcome is inconsistent"):
        StepExecutionResult.permanent_failure(
            "spreadsheet_quality_blocked",
            quality_status="passed",
            download_allowed=True,
            quality_report_schema_version="workbook-quality-report.v1",
        )


async def test_outputs_fail_closed_when_checkpoint_asset_is_missing(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "combined-output-integrity-001"
    )
    await GenerationWorkerService(
        generation_harness.session_factory,
        AllowAllCredentialLimiter(),
    ).process(
        created.task_id,
        ControlledStepExecutor(
            [
                StepExecutionResult.succeeded(
                    output_asset_id=PPT_ASSET_ID,
                    asset_version=f"sha256:{'a' * 64}",
                    quality_status="passed",
                    download_allowed=True,
                    quality_report_schema_version="presentation-quality-report.v1",
                )
            ]
        ),
    )

    with pytest.raises(GenerationOperationError) as captured:
        await generation_harness.service.outputs(
            "access-token",
            created.task_id,
        )

    assert captured.value.error_code == "generation_output_integrity_failed"


async def test_bare_executor_result_preserves_quality_checkpoint_metadata(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "combined-preserve-checkpoint-001"
    )

    processed = await GenerationWorkerService(
        generation_harness.session_factory,
        AllowAllCredentialLimiter(),
    ).process(
        created.task_id,
        CheckpointingExecutor(generation_harness.session_factory),
    )

    assert processed.steps[0].output_asset_id == PPT_ASSET_ID
    assert processed.steps[0].quality_status == "passed"
    assert processed.steps[0].download_allowed is True


async def test_retry_preserves_durable_renderer_checkpoint(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "combined-preserve-retry-checkpoint-001"
    )
    executor = RetryingCheckpointExecutor(generation_harness.session_factory)
    worker = GenerationWorkerService(
        generation_harness.session_factory,
        AllowAllCredentialLimiter(),
    )

    retrying = await worker.process(created.task_id, executor)
    processed = await worker.process(created.task_id, executor)

    assert retrying.status == "queued"
    assert processed.status == "succeeded"
    assert executor.calls == 2


async def test_rendered_asset_can_remain_quality_pending_without_integrity_error(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "combined-quality-pending-001"
    )
    async with generation_harness.session_factory() as session, session.begin():
        task = await session.get(GenerationTask, created.task_id, with_for_update=True)
        step = await session.scalar(
            select(GenerationTaskStep)
            .where(GenerationTaskStep.task_id == task.id)
            .with_for_update()
        )
        step.checkpoint = {"output_asset_id": str(PPT_ASSET_ID)}
        session.add(
            FileAsset(
                id=PPT_ASSET_ID,
                user_id=USER_ID,
                project_id=PROJECT_ID,
                original_filename="sales-presentation.pptx",
                file_category="presentation",
                mime_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "presentationml.presentation"
                ),
                byte_size=1024,
                sha256="a" * 64,
                storage_provider="local",
                storage_key=(
                    f"users/{USER_ID}/outputs/{PPT_ASSET_ID}/presentation.pptx"
                ),
                processing_status="ready",
                generated_task_id=task.id,
                processing_warnings=[],
            )
        )

    snapshot = await generation_harness.service.get(
        "access-token",
        created.task_id,
    )

    assert snapshot.steps[0].output_asset_id == PPT_ASSET_ID
    assert snapshot.steps[0].quality_status is None
    assert snapshot.steps[0].download_allowed is False
