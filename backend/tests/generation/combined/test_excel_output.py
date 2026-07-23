from pathlib import Path

from sqlalchemy import select

from app.models.file_assets import FileAsset
from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.services.renderers.excel.contracts import WorkbookPlan
from app.services.renderers.excel.output_store import ExcelOutputStore
from app.services.renderers.excel.renderer import ExcelRenderer
from app.services.renderers.excel.service import ExcelOutputService
from tests.generation.conftest import BRIEF_ID
from tests.renderers.spreadsheet.test_contracts import valid_workbook_plan


async def test_excel_output_service_persists_generation_asset_and_replays(
    generation_harness,
    tmp_path: Path,
) -> None:
    await generation_harness.set_combined()
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "combined-excel-output-001"
    )
    async with generation_harness.session_factory() as session, session.begin():
        task = await session.get(GenerationTask, created.task_id, with_for_update=True)
        step = await session.scalar(
            select(GenerationTaskStep)
            .where(
                GenerationTaskStep.task_id == task.id,
                GenerationTaskStep.output_kind == "xlsx",
            )
            .with_for_update()
        )
        task.status = "running"
        step.status = "running"
        step.attempt = 1
    root = tmp_path / "files"
    root.mkdir()
    service = ExcelOutputService(
        generation_harness.session_factory,
        ExcelRenderer(),
        ExcelOutputStore(root),
    )
    plan = WorkbookPlan.validate_for_renderer(valid_workbook_plan())

    first = await service.render(created.task_id, step.id, plan)
    replay = await service.render(created.task_id, step.id, plan)

    async with generation_harness.session_factory() as session:
        asset = await session.get(FileAsset, first.asset_id)
        persisted_step = await session.get(GenerationTaskStep, step.id)

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.asset_id == first.asset_id
    assert asset.generated_task_id == created.task_id
    assert asset.file_category == "spreadsheet"
    assert asset.processing_status == "ready"
    assert asset.sha256 == first.sha256
    assert asset.storage_key == (
        f"users/{asset.user_id}/outputs/{asset.id}/analysis.xlsx"
    )
    assert (root / Path(*asset.storage_key.split("/"))).is_file()
    assert persisted_step.checkpoint["output_asset_id"] == str(asset.id)
    assert persisted_step.checkpoint["excel_plan_checksum"] == first.plan_sha256
    assert persisted_step.checkpoint["renderer_result"]["sha256"] == first.sha256
