from uuid import UUID

from app.services.generation_combined import CombinedGenerationExecutor
from app.services.generation_worker import (
    GenerationWorkerService,
    StepExecutionResult,
)
from tests.generation.conftest import BRIEF_ID


class AllowAllCredentialLimiter:
    async def acquire(self, **_kwargs) -> bool:
        return True


class RecordingPipeline:
    def __init__(self, result: StepExecutionResult) -> None:
        self.result = result
        self.calls = []

    async def execute(self, context):
        self.calls.append(context)
        return self.result


async def test_combined_executor_routes_two_skills_by_output_kind(
    generation_harness,
) -> None:
    await generation_harness.set_combined()
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "combined-router-001"
    )
    ppt = RecordingPipeline(
        StepExecutionResult.succeeded(
            output_asset_id=UUID("019f6000-0000-7000-8000-000000000061"),
            asset_version=f"sha256:{'a' * 64}",
            quality_status="passed",
            download_allowed=True,
            quality_report_schema_version="presentation-quality-report.v1",
        )
    )
    spreadsheet = RecordingPipeline(
        StepExecutionResult.succeeded(
            output_asset_id=UUID("019f6000-0000-7000-8000-000000000062"),
            asset_version=f"sha256:{'b' * 64}",
            quality_status="passed",
            download_allowed=True,
            quality_report_schema_version="workbook-quality-report.v1",
        )
    )

    processed = await GenerationWorkerService(
        generation_harness.session_factory,
        AllowAllCredentialLimiter(),
    ).process(
        created.task_id,
        CombinedGenerationExecutor(
            presentation_pipeline=ppt,
            spreadsheet_pipeline=spreadsheet,
        ),
    )

    assert processed.status == "succeeded"
    assert [call.output_kind for call in ppt.calls] == ["pptx"]
    assert [call.output_kind for call in spreadsheet.calls] == ["xlsx"]
    assert ppt.calls[0].task_id == spreadsheet.calls[0].task_id == created.task_id
    assert ppt.calls[0].model_snapshot == spreadsheet.calls[0].model_snapshot
