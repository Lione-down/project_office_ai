import pytest
from sqlalchemy import func, select

from app.models.file_assets import FileAsset
from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.services.renderers.presentation.service import PresentationOutputError
from tests.renderers.presentation.conftest import (
    FailingRendererClient,
    STEP_ID,
    TASK_ID,
)
from tests.renderers.presentation.test_contracts import valid_plan


async def test_render_persists_one_immutable_task_output_and_replays(
    output_harness,
) -> None:
    first = await output_harness.service.render(TASK_ID, STEP_ID, valid_plan())
    replay = await output_harness.service.render(TASK_ID, STEP_ID, valid_plan())

    async with output_harness.session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(FileAsset))
        asset = await session.get(FileAsset, first.asset_id)
        step = await session.get(GenerationTaskStep, STEP_ID)

    assert count == 1
    assert replay.asset_id == first.asset_id
    assert first.replayed is False
    assert replay.replayed is True
    assert len(output_harness.client.calls) == 1
    assert asset.processing_status == "ready"
    assert asset.generated_task_id == TASK_ID
    assert asset.byte_size == len(b"synthetic-renderer-output")
    assert step.checkpoint["output_asset_id"] == str(first.asset_id)
    assert "output_storage_key" not in step.checkpoint
    assert "path" not in str(step.checkpoint).lower()


async def test_task_retry_creates_a_new_immutable_output_asset(
    output_harness,
) -> None:
    first = await output_harness.service.render(TASK_ID, STEP_ID, valid_plan())
    async with output_harness.session_factory() as session, session.begin():
        task = await session.get(GenerationTask, TASK_ID)
        step = await session.get(GenerationTaskStep, STEP_ID)
        task.retry_count = 1
        step.checkpoint = {}

    retried = await output_harness.service.render(TASK_ID, STEP_ID, valid_plan())

    async with output_harness.session_factory() as session:
        assets = list(
            await session.scalars(
                select(FileAsset).order_by(FileAsset.created_at, FileAsset.id)
            )
        )

    assert retried.asset_id != first.asset_id
    assert len(assets) == 2
    assert len(output_harness.client.calls) == 2


async def test_existing_step_rejects_a_different_plan(output_harness) -> None:
    await output_harness.service.render(TASK_ID, STEP_ID, valid_plan())
    changed = valid_plan()
    changed["metadata"]["title"] = "不同的汇报"

    with pytest.raises(PresentationOutputError, match="presentation_plan_conflict"):
        await output_harness.service.render(TASK_ID, STEP_ID, changed)

    assert len(output_harness.client.calls) == 1


async def test_plan_template_must_match_the_frozen_task_snapshot(
    output_harness,
) -> None:
    changed = valid_plan()
    changed["template"] = {
        "code": "ppt.operating-review.v1",
        "version": "1.0.0",
    }

    with pytest.raises(PresentationOutputError, match="presentation_template_conflict"):
        await output_harness.service.render(TASK_ID, STEP_ID, changed)

    assert len(output_harness.client.calls) == 0


async def test_finalization_failure_recovers_without_overwrite(
    output_harness, monkeypatch
) -> None:
    original_finalize = output_harness.service._finalize

    async def fail_finalize(*_args, **_kwargs):
        raise RuntimeError("simulated finalization failure")

    monkeypatch.setattr(output_harness.service, "_finalize", fail_finalize)
    with pytest.raises(RuntimeError, match="simulated finalization failure"):
        await output_harness.service.render(TASK_ID, STEP_ID, valid_plan())

    async with output_harness.session_factory() as session:
        asset = await session.scalar(select(FileAsset))
        assert asset.processing_status == "parsing"
        stored = output_harness.output_store.inspect(asset.user_id, asset.id)
        assert stored is not None

    monkeypatch.setattr(output_harness.service, "_finalize", original_finalize)
    recovered = await output_harness.service.render(TASK_ID, STEP_ID, valid_plan())

    assert recovered.asset_id == asset.id
    assert recovered.replayed is True
    assert len(output_harness.client.calls) == 1


async def test_ready_replay_revalidates_the_immutable_file(
    output_harness,
) -> None:
    completed = await output_harness.service.render(TASK_ID, STEP_ID, valid_plan())
    async with output_harness.session_factory() as session:
        asset = await session.get(FileAsset, completed.asset_id)
    stored = output_harness.output_store.inspect(asset.user_id, asset.id)
    stored.path.unlink()

    with pytest.raises(
        PresentationOutputError, match="presentation_output_integrity_failed"
    ):
        await output_harness.service.render(TASK_ID, STEP_ID, valid_plan())


async def test_renderer_start_is_checkpointed_before_external_call(
    output_harness,
) -> None:
    output_harness.service._renderer = FailingRendererClient()

    with pytest.raises(RuntimeError, match="simulated renderer failure"):
        await output_harness.service.render(TASK_ID, STEP_ID, valid_plan())

    async with output_harness.session_factory() as session:
        step = await session.get(GenerationTaskStep, STEP_ID)
        asset = await session.scalar(select(FileAsset))

    assert step.checkpoint["renderer_call_started"] is True
    assert "renderer_call_completed" not in step.checkpoint
    assert asset.processing_status == "parsing"


async def test_rejects_non_ppt_or_foreign_step(output_harness) -> None:
    with pytest.raises(PresentationOutputError, match="presentation_step_invalid"):
        await output_harness.service.render(
            TASK_ID,
            STEP_ID.__class__("019f5000-0000-7000-8000-000000000299"),
            valid_plan(),
        )
