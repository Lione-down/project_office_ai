from dataclasses import dataclass
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.base import utc_now
from app.models.file_assets import FileAsset
from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.services.generation_worker import StepExecutionResult
from app.services.quality.spreadsheet.artifact_store import (
    SpreadsheetQualityArtifactStore,
    StoredSpreadsheetQualityArtifacts,
)
from app.services.quality.spreadsheet.contracts import (
    SpreadsheetQualityConflict,
    SpreadsheetQualityFinding,
    SpreadsheetQualityReport,
    SpreadsheetSourceReference,
    SpreadsheetValidationReference,
)
from app.services.quality.spreadsheet.inspector import SpreadsheetQualityInspector
from app.services.renderers.excel.contracts import (
    WorkbookPlan,
    workbook_plan_sha256,
)
from app.services.renderers.excel.libreoffice import WorkbookValidationError
from app.services.renderers.excel.renderer import RenderedWorkbook


class SpreadsheetQualityError(RuntimeError):
    pass


@dataclass(frozen=True)
class SpreadsheetQualityOutcome:
    report: SpreadsheetQualityReport
    report_key: str
    report_sha256: str
    validated_key: str | None
    replayed: bool

    def step_result(self) -> StepExecutionResult:
        common = {
            "output_asset_id": self.report.source.asset_id,
            "asset_version": f"sha256:{self.report.source.sha256}",
            "quality_status": self.report.status,
            "download_allowed": self.report.download_allowed,
            "quality_report_schema_version": self.report.schema_version,
        }
        if self.report.download_allowed:
            return StepExecutionResult.succeeded(**common)
        return StepExecutionResult.permanent_failure(
            "spreadsheet_quality_blocked",
            **common,
        )


@dataclass(frozen=True)
class _PendingQuality:
    asset_id: UUID
    user_id: UUID
    task_id: UUID
    step_id: UUID
    source_sha256: str
    source_byte_size: int
    plan_sha256: str
    renderer_version: str
    template_code: str
    template_version: str
    report_key: str | None
    report_sha256: str | None


class SpreadsheetQualityService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        libreoffice_client,
        artifacts: SpreadsheetQualityArtifactStore,
        *,
        inspector: SpreadsheetQualityInspector | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._libreoffice = libreoffice_client
        self._artifacts = artifacts
        self._inspector = inspector or SpreadsheetQualityInspector()

    async def evaluate(
        self,
        asset_id: UUID,
        step_id: UUID,
        plan: WorkbookPlan,
        *,
        conflicts: tuple[SpreadsheetQualityConflict, ...] = (),
    ) -> SpreadsheetQualityOutcome:
        pending = await self._prepare(asset_id, step_id, plan)
        if pending.report_key is not None and pending.report_sha256 is not None:
            report, stored = self._artifacts.load(
                pending.user_id,
                pending.asset_id,
                pending.report_key,
                pending.report_sha256,
            )
            return self._outcome(report, stored, replayed=True)
        rendered = self._rendered(pending)
        try:
            validation = await self._libreoffice.recalculate(
                request_id=pending.step_id,
                user_id=pending.user_id,
                asset_id=pending.asset_id,
                source_sha256=pending.source_sha256,
                source_byte_size=pending.source_byte_size,
                plan_sha256=pending.plan_sha256,
                renderer_version=pending.renderer_version,
                template_code=pending.template_code,
                template_version=pending.template_version,
            )
            report = self._inspector.inspect(
                asset_id=pending.asset_id,
                rendered=rendered,
                plan=plan,
                validation_copy=validation.validation_copy.path,
                validation_report=validation.report,
                validation_report_sha256=validation.report_artifact.sha256,
                conflicts=conflicts,
            )
            validation_copy = validation.validation_copy.path
            validation_report_path = validation.report_artifact.path
        except WorkbookValidationError as exception:
            report = self._blocked_report(pending, self._safe_code(exception))
            validation_copy = None
            validation_report_path = None
        stored = self._artifacts.persist(
            pending.user_id,
            pending.asset_id,
            report,
            validation_copy=validation_copy,
            validation_report_path=validation_report_path,
        )
        return await self._finalize(pending, report, stored)

    async def _prepare(
        self, asset_id: UUID, step_id: UUID, plan: WorkbookPlan
    ) -> _PendingQuality:
        plan_sha256 = workbook_plan_sha256(plan)
        async with self._session_factory() as session, session.begin():
            asset = await session.get(FileAsset, asset_id, with_for_update=True)
            step = await session.get(GenerationTaskStep, step_id, with_for_update=True)
            task = (
                await session.get(GenerationTask, step.task_id, with_for_update=True)
                if step is not None
                else None
            )
            checkpoint = dict(step.checkpoint or {}) if step is not None else {}
            renderer_result = checkpoint.get("renderer_result")
            if (
                asset is None
                or step is None
                or task is None
                or asset.generated_task_id != task.id
                or step.step_key != "render:xlsx"
                or step.output_kind != "xlsx"
                or asset.file_category != "spreadsheet"
                or asset.processing_status != "ready"
                or checkpoint.get("output_asset_id") != str(asset.id)
                or checkpoint.get("excel_plan_checksum") != plan_sha256
                or checkpoint.get("renderer_version") != plan.renderer_version
                or checkpoint.get("template_code") != plan.template.code
                or checkpoint.get("template_version") != plan.template.version
                or not isinstance(renderer_result, dict)
                or renderer_result.get("sha256") != asset.sha256
                or renderer_result.get("byte_size") != asset.byte_size
                or renderer_result.get("plan_sha256") != plan_sha256
            ):
                raise SpreadsheetQualityError("spreadsheet_quality_input_invalid")
            if asset.quality_status is None:
                if task.status != "running" or step.status != "running":
                    raise SpreadsheetQualityError("spreadsheet_quality_step_invalid")
                checkpoint["quality_gate_started"] = True
                checkpoint["quality_engine_version"] = "spreadsheet-quality.v1"
                step.checkpoint = checkpoint
            return _PendingQuality(
                asset_id=asset.id,
                user_id=asset.user_id,
                task_id=task.id,
                step_id=step.id,
                source_sha256=asset.sha256,
                source_byte_size=asset.byte_size,
                plan_sha256=plan_sha256,
                renderer_version=plan.renderer_version,
                template_code=plan.template.code,
                template_version=plan.template.version,
                report_key=asset.quality_report_key,
                report_sha256=asset.quality_report_sha256,
            )

    async def _finalize(
        self,
        pending: _PendingQuality,
        report: SpreadsheetQualityReport,
        stored: StoredSpreadsheetQualityArtifacts,
    ) -> SpreadsheetQualityOutcome:
        async with self._session_factory() as session, session.begin():
            asset = await session.get(FileAsset, pending.asset_id, with_for_update=True)
            step = await session.get(
                GenerationTaskStep, pending.step_id, with_for_update=True
            )
            if (
                asset is None
                or step is None
                or asset.sha256 != pending.source_sha256
                or asset.byte_size != pending.source_byte_size
            ):
                raise SpreadsheetQualityError("spreadsheet_quality_source_changed")
            if asset.quality_status is not None:
                if (
                    asset.quality_status != report.status
                    or asset.quality_report_key != stored.report_key
                    or asset.quality_report_sha256 != stored.report_sha256
                ):
                    raise SpreadsheetQualityError("spreadsheet_quality_state_conflict")
                return self._outcome(report, stored, replayed=True)
            asset.quality_status = report.status
            asset.quality_report_key = stored.report_key
            asset.quality_report_sha256 = stored.report_sha256
            asset.quality_report_schema_version = report.schema_version
            asset.quality_engine_version = report.quality_engine_version
            asset.quality_preview_keys = []
            asset.quality_validated_key = stored.validated_key
            asset.quality_validated_sha256 = stored.validated_sha256
            asset.quality_validated_byte_size = stored.validated_byte_size
            asset.quality_repair_attempt_count = 0
            asset.quality_checked_at = report.generated_at
            checkpoint = dict(step.checkpoint or {})
            checkpoint.update(
                {
                    "quality_gate_completed": True,
                    "quality_status": report.status,
                    "quality_report_schema_version": report.schema_version,
                    "quality_report_sha256": stored.report_sha256,
                    "quality_engine_version": report.quality_engine_version,
                    "quality_repair_attempt_count": 0,
                    "quality_download_allowed": report.download_allowed,
                    "asset_version": f"sha256:{asset.sha256}",
                }
            )
            step.checkpoint = checkpoint
        return self._outcome(report, stored, replayed=False)

    def _rendered(self, pending: _PendingQuality) -> RenderedWorkbook:
        return RenderedWorkbook(
            path=self._artifacts.source_path(pending.user_id, pending.asset_id),
            sha256=pending.source_sha256,
            byte_size=pending.source_byte_size,
            plan_sha256=pending.plan_sha256,
            schema_version="workbook-plan.v1",
            renderer_version=pending.renderer_version,
            template_code=pending.template_code,
            template_version=pending.template_version,
            sheet_count=0,
            generated_cell_count=0,
        )

    @staticmethod
    def _blocked_report(
        pending: _PendingQuality, error_code: str
    ) -> SpreadsheetQualityReport:
        return SpreadsheetQualityReport(
            schema_version="workbook-quality-report.v1",
            quality_engine_version="spreadsheet-quality.v1",
            source=SpreadsheetSourceReference(
                asset_id=pending.asset_id,
                sha256=pending.source_sha256,
                byte_size=pending.source_byte_size,
                plan_sha256=pending.plan_sha256,
                renderer_version=pending.renderer_version,
                template_code=pending.template_code,
                template_version=pending.template_version,
            ),
            validation=SpreadsheetValidationReference(
                status="failed",
                error_code=error_code,
            ),
            status="blocked",
            download_allowed=False,
            findings=(
                SpreadsheetQualityFinding(
                    code="workbook_open_failed",
                    severity="blocker",
                    rule_version="spreadsheet-open.v1",
                ),
            ),
            generated_at=utc_now(),
        )

    @staticmethod
    def _safe_code(exception: Exception) -> str:
        code = getattr(exception, "error_code", str(exception))
        if (
            not isinstance(code, str)
            or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", code) is None
        ):
            return "libreoffice_recalculation_failed"
        return code

    @staticmethod
    def _outcome(
        report: SpreadsheetQualityReport,
        stored: StoredSpreadsheetQualityArtifacts,
        *,
        replayed: bool,
    ) -> SpreadsheetQualityOutcome:
        return SpreadsheetQualityOutcome(
            report=report,
            report_key=stored.report_key,
            report_sha256=stored.report_sha256,
            validated_key=stored.validated_key,
            replayed=replayed,
        )
