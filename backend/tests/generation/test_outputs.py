from uuid import UUID

from app.models.generation_task_steps import GenerationTaskStep
from app.services.generation_outputs import generation_step_snapshot


def test_failed_partial_output_is_not_exposed_as_a_completed_asset() -> None:
    step = GenerationTaskStep(
        task_id=UUID("019f5000-0000-7000-8000-000000000301"),
        step_key="render:pptx",
        output_kind="pptx",
        status="failed",
        attempt=1,
        estimated_credits=800,
        checkpoint={
            "output_asset_id": "019f5000-0000-7000-8000-000000000302",
            "presentation_plan_checksum": "a" * 64,
        },
        token_estimate=0,
        error_category="worker_execution_failed",
    )

    snapshot = generation_step_snapshot(step)

    assert snapshot.output_asset_id is None
    assert snapshot.quality_status is None
    assert snapshot.download_allowed is False
