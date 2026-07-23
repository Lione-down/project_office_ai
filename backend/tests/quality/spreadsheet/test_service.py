from hashlib import sha256
import json
from pathlib import Path
import shutil
from uuid import UUID

from sqlalchemy import select

from app.models.file_assets import FileAsset
from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.services.quality.spreadsheet.artifact_store import (
    SpreadsheetQualityArtifactStore,
)
from app.services.quality.spreadsheet.contracts import SpreadsheetQualityConflict
from app.services.quality.spreadsheet.service import SpreadsheetQualityService
from app.services.renderers.excel.contracts import (
    WorkbookPlan,
    workbook_plan_sha256,
)
from app.services.renderers.excel.libreoffice import WorkbookValidationReport
from app.services.renderers.excel.sidecar import (
    VerifiedSpreadsheetArtifact,
    VerifiedSpreadsheetValidation,
)
from tests.generation.conftest import (
    BRIEF_ID,
    PROJECT_ID,
    USER_ID,
    generation_harness as _generation_harness,  # noqa: F401
)
from tests.renderers.spreadsheet.test_contracts import valid_workbook_plan
from tests.renderers.spreadsheet.test_renderer import render_sample


ASSET_ID = UUID("019f6000-0000-7000-8000-000000000051")


class FakeLibreOfficeClient:
    def __init__(self, validation: VerifiedSpreadsheetValidation) -> None:
        self.validation = validation
        self.calls: list[dict] = []

    async def recalculate(self, **kwargs) -> VerifiedSpreadsheetValidation:
        self.calls.append(kwargs)
        return self.validation


def verified_validation(tmp_path: Path, rendered) -> VerifiedSpreadsheetValidation:
    validation_copy = tmp_path / "verified" / "analysis.xlsx"
    validation_copy.parent.mkdir()
    shutil.copyfile(rendered.path, validation_copy)
    report = WorkbookValidationReport(
        schema_version="workbook-validation-report.v1",
        original_sha256=rendered.sha256,
        validation_sha256=sha256(validation_copy.read_bytes()).hexdigest(),
        plan_sha256=rendered.plan_sha256,
        renderer_version=rendered.renderer_version,
        template_code=rendered.template_code,
        template_version=rendered.template_version,
        libreoffice_version="LibreOffice 25.2.3",
        formula_count=12,
        difference_count=0,
        differences=(),
    )
    report_path = tmp_path / "verified" / "validation-report.json"
    report_bytes = json.dumps(
        report.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    report_path.write_bytes(report_bytes)
    return VerifiedSpreadsheetValidation(
        validation_copy=VerifiedSpreadsheetArtifact(
            validation_copy,
            report.validation_sha256,
            validation_copy.stat().st_size,
        ),
        report_artifact=VerifiedSpreadsheetArtifact(
            report_path,
            sha256(report_bytes).hexdigest(),
            len(report_bytes),
        ),
        report=report,
    )


async def prepare_quality_input(generation_harness, tmp_path: Path):
    await generation_harness.set_combined()
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "spreadsheet-quality-service-001"
    )
    plan = WorkbookPlan.validate_for_renderer(valid_workbook_plan())
    root = tmp_path / "files"
    output = root / "users" / str(USER_ID) / "outputs" / str(ASSET_ID) / "analysis.xlsx"
    output.parent.mkdir(parents=True)
    rendered = render_sample(output)
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
        step.checkpoint = {
            "output_asset_id": str(ASSET_ID),
            "excel_plan_checksum": workbook_plan_sha256(plan),
            "renderer_version": rendered.renderer_version,
            "template_code": rendered.template_code,
            "template_version": rendered.template_version,
            "renderer_result": {
                "sha256": rendered.sha256,
                "byte_size": rendered.byte_size,
                "plan_sha256": rendered.plan_sha256,
            },
        }
        session.add(
            FileAsset(
                id=ASSET_ID,
                user_id=USER_ID,
                project_id=PROJECT_ID,
                original_filename="sales-analysis.xlsx",
                file_category="spreadsheet",
                mime_type=(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                byte_size=rendered.byte_size,
                sha256=rendered.sha256,
                storage_provider="local",
                storage_key=f"users/{USER_ID}/outputs/{ASSET_ID}/analysis.xlsx",
                processing_status="ready",
                generated_task_id=task.id,
                processing_warnings=[],
            )
        )
    return created, plan, rendered, root


async def test_service_persists_quality_artifacts_checkpoint_and_replays(
    _generation_harness,  # noqa: F811
    tmp_path: Path,
) -> None:
    created, plan, rendered, root = await prepare_quality_input(
        _generation_harness, tmp_path
    )
    validation = verified_validation(tmp_path, rendered)
    client = FakeLibreOfficeClient(validation)
    service = SpreadsheetQualityService(
        _generation_harness.session_factory,
        client,
        SpreadsheetQualityArtifactStore(root),
    )
    quality_dir = root / "users" / str(USER_ID) / "outputs" / str(ASSET_ID) / "quality"
    quality_dir.mkdir()
    (quality_dir / ".validated.xlsx.tmp").write_bytes(b"stale-crash-temp")
    async with _generation_harness.session_factory() as session:
        step_id = await session.scalar(
            select(GenerationTaskStep.id).where(
                GenerationTaskStep.task_id == created.task_id,
                GenerationTaskStep.output_kind == "xlsx",
            )
        )

    first = await service.evaluate(ASSET_ID, step_id, plan)
    replay = await service.evaluate(ASSET_ID, step_id, plan)

    async with _generation_harness.session_factory() as session:
        asset = await session.get(FileAsset, ASSET_ID)
        step = await session.get(GenerationTaskStep, step_id)

    assert first.report.status == "passed"
    assert first.step_result().output_asset_id == ASSET_ID
    assert first.step_result().asset_version == f"sha256:{rendered.sha256}"
    assert first.step_result().download_allowed is True
    assert replay.replayed is True
    assert len(client.calls) == 1
    assert asset.quality_report_schema_version == "workbook-quality-report.v1"
    assert asset.quality_validated_key == (
        f"users/{USER_ID}/outputs/{ASSET_ID}/quality/validated.xlsx"
    )
    assert (
        root
        / "users"
        / str(USER_ID)
        / "outputs"
        / str(ASSET_ID)
        / "quality"
        / "libreoffice-report.json"
    ).is_file()
    assert step.checkpoint["quality_gate_completed"] is True
    assert step.checkpoint["quality_status"] == "passed"


async def test_service_persists_unresolved_unit_conflict_as_blocker(
    _generation_harness,  # noqa: F811
    tmp_path: Path,
) -> None:
    created, plan, rendered, root = await prepare_quality_input(
        _generation_harness, tmp_path
    )
    service = SpreadsheetQualityService(
        _generation_harness.session_factory,
        FakeLibreOfficeClient(verified_validation(tmp_path, rendered)),
        SpreadsheetQualityArtifactStore(root),
    )
    async with _generation_harness.session_factory() as session:
        step_id = await session.scalar(
            select(GenerationTaskStep.id).where(
                GenerationTaskStep.task_id == created.task_id,
                GenerationTaskStep.output_kind == "xlsx",
            )
        )

    outcome = await service.evaluate(
        ASSET_ID,
        step_id,
        plan,
        conflicts=(
            SpreadsheetQualityConflict(
                kind="unit",
                code="unit_conflict",
                resolved=False,
            ),
        ),
    )

    async with _generation_harness.session_factory() as session:
        asset = await session.get(FileAsset, ASSET_ID)

    assert outcome.report.status == "blocked"
    assert outcome.validated_key is None
    assert outcome.step_result().status == "permanent_failure"
    assert asset.quality_status == "blocked"
    assert asset.quality_validated_key is None
    assert (
        root
        / "users"
        / str(USER_ID)
        / "outputs"
        / str(ASSET_ID)
        / "quality"
        / "validation-copy.xlsx"
    ).is_file()
