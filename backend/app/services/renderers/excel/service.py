from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.base import new_uuid7, utc_now
from app.models.file_assets import FileAsset
from app.models.generation_task_inputs import GenerationTaskInput
from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.services.renderers.excel.contracts import (
    WorkbookPlan,
    workbook_plan_sha256,
)
from app.services.renderers.excel.output_store import (
    ExcelOutputStore,
    ExcelOutputStoreError,
    StoredExcelOutput,
)
from app.services.renderers.excel.renderer import ExcelRenderer, RenderedWorkbook


class ExcelOutputError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExcelOutputSnapshot:
    asset_id: UUID
    task_id: UUID
    sha256: str
    byte_size: int
    plan_sha256: str
    renderer_version: str
    template_code: str
    template_version: str
    replayed: bool


@dataclass(frozen=True)
class _PendingOutput:
    asset_id: UUID
    user_id: UUID
    task_id: UUID
    step_id: UUID
    plan_sha256: str
    renderer_version: str
    template_code: str
    template_version: str
    sheet_count: int
    generated_cell_count: int
    created: bool
    completed: ExcelOutputSnapshot | None
    renderer_result: dict | None


class ExcelOutputService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        renderer: ExcelRenderer,
        output_store: ExcelOutputStore,
    ) -> None:
        self._session_factory = session_factory
        self._renderer = renderer
        self._outputs = output_store

    async def render(
        self,
        task_id: UUID,
        step_id: UUID,
        plan: WorkbookPlan | dict,
    ) -> ExcelOutputSnapshot:
        validated = (
            plan
            if isinstance(plan, WorkbookPlan)
            else WorkbookPlan.validate_for_renderer(plan)
        )
        plan_sha256 = workbook_plan_sha256(validated)
        pending = await self._prepare(task_id, step_id, validated, plan_sha256)
        if pending.completed is not None:
            stored = self._outputs.inspect(pending.user_id, pending.asset_id)
            if (
                stored is None
                or stored.sha256 != pending.completed.sha256
                or stored.byte_size != pending.completed.byte_size
            ):
                raise ExcelOutputError("excel_output_integrity_failed")
            return pending.completed
        stored = self._recover_stored(pending)
        if stored is None:
            await self._mark_renderer_started(pending)
            with TemporaryDirectory(prefix="office-ai-excel-render-") as temporary:
                rendered = self._renderer.render(
                    validated,
                    Path(temporary) / "analysis.xlsx",
                )
                result = self._renderer_result(rendered)
                self._verify_renderer_result(pending, result)
                await self._record_renderer_result(pending, result)
                stored = self._persist_or_recover(pending, rendered)
        else:
            result = pending.renderer_result
            if result is None:
                raise ExcelOutputError("excel_checkpoint_invalid")
            self._verify_renderer_result(pending, result)
        return await self._finalize(
            pending,
            stored,
            result,
            replayed=not pending.created,
        )

    async def _prepare(
        self,
        task_id: UUID,
        step_id: UUID,
        plan: WorkbookPlan,
        plan_sha256: str,
    ) -> _PendingOutput:
        async with self._session_factory() as session, session.begin():
            task = await session.get(GenerationTask, task_id, with_for_update=True)
            step = await session.get(GenerationTaskStep, step_id, with_for_update=True)
            if (
                task is None
                or step is None
                or step.task_id != task.id
                or step.output_kind != "xlsx"
                or step.step_key != "render:xlsx"
            ):
                raise ExcelOutputError("excel_step_invalid")
            await self._verify_template(session, task, plan)
            idempotency_key = self._idempotency_key(step.id)
            asset = await session.scalar(
                select(FileAsset)
                .where(
                    FileAsset.user_id == task.user_id,
                    FileAsset.idempotency_key == idempotency_key,
                )
                .with_for_update()
            )
            created = asset is None
            if (asset is None or asset.processing_status != "ready") and (
                task.status != "running" or step.status != "running"
            ):
                raise ExcelOutputError("excel_step_invalid")
            if asset is None:
                asset_id = new_uuid7()
                asset = FileAsset(
                    id=asset_id,
                    user_id=task.user_id,
                    project_id=task.project_id,
                    original_filename="sales-analysis.xlsx",
                    file_category="spreadsheet",
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    byte_size=0,
                    sha256="0" * 64,
                    storage_provider="local",
                    storage_key=self._outputs.build_key(task.user_id, asset_id),
                    processing_status="parsing",
                    idempotency_key=idempotency_key,
                    generated_task_id=task.id,
                    processing_warnings=[],
                    parser_name="xlsxwriter",
                    parser_version=plan.renderer_version,
                    processing_started_at=utc_now(),
                )
                session.add(asset)
            checkpoint = dict(step.checkpoint or {})
            existing_checksum = checkpoint.get("excel_plan_checksum")
            if existing_checksum is not None and existing_checksum != plan_sha256:
                raise ExcelOutputError("excel_plan_conflict")
            checkpoint.update(
                {
                    "provider_call_started": False,
                    "renderer_call_started": checkpoint.get(
                        "renderer_call_started", False
                    ),
                    "output_asset_id": str(asset.id),
                    "excel_plan_checksum": plan_sha256,
                    "renderer_version": plan.renderer_version,
                    "template_code": plan.template.code,
                    "template_version": plan.template.version,
                    "sheet_count": len(plan.sheets),
                    "generated_cell_count": sum(
                        sheet.generated_cell_count for sheet in plan.sheets
                    ),
                }
            )
            step.checkpoint = checkpoint
            await session.flush()
            common = self._pending_fields(task, step, asset, plan, plan_sha256)
            if asset.processing_status == "ready":
                return _PendingOutput(
                    **common,
                    created=False,
                    completed=self._snapshot(asset, checkpoint, replayed=True),
                    renderer_result=None,
                )
            if asset.processing_status != "parsing":
                raise ExcelOutputError("excel_output_state_invalid")
            return _PendingOutput(
                **common,
                created=created,
                completed=None,
                renderer_result=checkpoint.get("renderer_result"),
            )

    @staticmethod
    async def _verify_template(
        session: AsyncSession,
        task: GenerationTask,
        plan: WorkbookPlan,
    ) -> None:
        template = await session.scalar(
            select(GenerationTaskInput).where(
                GenerationTaskInput.task_id == task.id,
                GenerationTaskInput.input_type == "template",
                GenerationTaskInput.reference_key
                == f"{plan.template.code}@{plan.template.version}",
            )
        )
        outputs = [item for item in task.skill_snapshot if item.get("kind") == "xlsx"]
        if (
            template is None
            or len(outputs) != 1
            or outputs[0].get("template_code") != plan.template.code
            or outputs[0].get("template_version") != plan.template.version
        ):
            raise ExcelOutputError("excel_template_conflict")

    async def _mark_renderer_started(self, pending: _PendingOutput) -> None:
        async with self._session_factory() as session, session.begin():
            step = await session.get(
                GenerationTaskStep, pending.step_id, with_for_update=True
            )
            asset = await session.get(FileAsset, pending.asset_id, with_for_update=True)
            if step is None or asset is None or asset.processing_status != "parsing":
                raise ExcelOutputError("excel_checkpoint_missing")
            checkpoint = dict(step.checkpoint or {})
            if checkpoint.get("excel_plan_checksum") != pending.plan_sha256:
                raise ExcelOutputError("excel_plan_conflict")
            checkpoint["renderer_call_started"] = True
            step.checkpoint = checkpoint

    async def _record_renderer_result(
        self, pending: _PendingOutput, result: dict
    ) -> None:
        async with self._session_factory() as session, session.begin():
            step = await session.get(
                GenerationTaskStep, pending.step_id, with_for_update=True
            )
            asset = await session.get(FileAsset, pending.asset_id, with_for_update=True)
            if step is None or asset is None or asset.processing_status != "parsing":
                raise ExcelOutputError("excel_checkpoint_missing")
            checkpoint = dict(step.checkpoint or {})
            if checkpoint.get("excel_plan_checksum") != pending.plan_sha256:
                raise ExcelOutputError("excel_plan_conflict")
            checkpoint["renderer_call_completed"] = True
            checkpoint["renderer_result"] = result
            step.checkpoint = checkpoint

    def _recover_stored(self, pending: _PendingOutput) -> StoredExcelOutput | None:
        if pending.renderer_result is None:
            return None
        stored = self._outputs.inspect(pending.user_id, pending.asset_id)
        if stored is not None:
            self._verify_stored(stored, pending.renderer_result)
        return stored

    def _persist_or_recover(
        self, pending: _PendingOutput, rendered: RenderedWorkbook
    ) -> StoredExcelOutput:
        result = self._renderer_result(rendered)
        existing = self._outputs.inspect(pending.user_id, pending.asset_id)
        if existing is not None:
            self._verify_stored(existing, result)
            return existing
        try:
            stored = self._outputs.persist(
                pending.user_id,
                pending.asset_id,
                rendered.path,
            )
        except ExcelOutputStoreError:
            stored = self._outputs.inspect(pending.user_id, pending.asset_id)
            if stored is None:
                raise
        self._verify_stored(stored, result)
        return stored

    async def _finalize(
        self,
        pending: _PendingOutput,
        stored: StoredExcelOutput,
        result: dict,
        *,
        replayed: bool,
    ) -> ExcelOutputSnapshot:
        self._verify_stored(stored, result)
        async with self._session_factory() as session, session.begin():
            asset = await session.get(FileAsset, pending.asset_id, with_for_update=True)
            step = await session.get(
                GenerationTaskStep, pending.step_id, with_for_update=True
            )
            if asset is None or step is None:
                raise ExcelOutputError("excel_checkpoint_missing")
            if asset.processing_status == "ready":
                return self._snapshot(asset, dict(step.checkpoint), replayed=True)
            if (
                asset.processing_status != "parsing"
                or asset.generated_task_id != pending.task_id
                or asset.storage_key != stored.storage_key
            ):
                raise ExcelOutputError("excel_output_state_invalid")
            asset.byte_size = stored.byte_size
            asset.sha256 = stored.sha256
            asset.processing_status = "ready"
            asset.processed_at = utc_now()
            checkpoint = dict(step.checkpoint or {})
            checkpoint["renderer_call_completed"] = True
            checkpoint["renderer_result"] = result
            step.checkpoint = checkpoint
            await session.flush()
            return self._snapshot(asset, checkpoint, replayed=replayed)

    @staticmethod
    def _verify_stored(stored: StoredExcelOutput, result: dict) -> None:
        if stored.sha256 != result.get("sha256") or stored.byte_size != result.get(
            "byte_size"
        ):
            raise ExcelOutputError("excel_output_integrity_failed")

    @staticmethod
    def _verify_renderer_result(pending: _PendingOutput, result: dict) -> None:
        if (
            result.get("plan_sha256") != pending.plan_sha256
            or result.get("renderer_version") != pending.renderer_version
            or result.get("template_code") != pending.template_code
            or result.get("template_version") != pending.template_version
            or result.get("sheet_count") != pending.sheet_count
            or result.get("generated_cell_count") != pending.generated_cell_count
        ):
            raise ExcelOutputError("excel_renderer_result_invalid")

    @staticmethod
    def _renderer_result(rendered: RenderedWorkbook) -> dict:
        return {
            "sha256": rendered.sha256,
            "byte_size": rendered.byte_size,
            "plan_sha256": rendered.plan_sha256,
            "renderer_version": rendered.renderer_version,
            "template_code": rendered.template_code,
            "template_version": rendered.template_version,
            "sheet_count": rendered.sheet_count,
            "generated_cell_count": rendered.generated_cell_count,
        }

    @staticmethod
    def _pending_fields(task, step, asset, plan, plan_sha256) -> dict:
        return {
            "asset_id": asset.id,
            "user_id": asset.user_id,
            "task_id": task.id,
            "step_id": step.id,
            "plan_sha256": plan_sha256,
            "renderer_version": plan.renderer_version,
            "template_code": plan.template.code,
            "template_version": plan.template.version,
            "sheet_count": len(plan.sheets),
            "generated_cell_count": sum(
                sheet.generated_cell_count for sheet in plan.sheets
            ),
        }

    @staticmethod
    def _idempotency_key(step_id: UUID) -> str:
        return f"render-output:{step_id}"

    @staticmethod
    def _snapshot(
        asset: FileAsset, checkpoint: dict, *, replayed: bool
    ) -> ExcelOutputSnapshot:
        result = checkpoint.get("renderer_result")
        if (
            asset.generated_task_id is None
            or not isinstance(result, dict)
            or result.get("sha256") != asset.sha256
            or result.get("byte_size") != asset.byte_size
        ):
            raise ExcelOutputError("excel_checkpoint_invalid")
        return ExcelOutputSnapshot(
            asset_id=asset.id,
            task_id=asset.generated_task_id,
            sha256=asset.sha256,
            byte_size=asset.byte_size,
            plan_sha256=result["plan_sha256"],
            renderer_version=result["renderer_version"],
            template_code=result["template_code"],
            template_version=result["template_version"],
            replayed=replayed,
        )
