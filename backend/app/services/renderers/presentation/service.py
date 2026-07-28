from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.base import new_uuid7, utc_now
from app.models.file_assets import FileAsset
from app.models.generation_task_inputs import GenerationTaskInput
from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.services.renderers.presentation.client import RenderedPresentation
from app.services.renderers.presentation.contracts import (
    PresentationPlan,
    presentation_plan_sha256,
)
from app.services.renderers.presentation.output_store import (
    PresentationOutputStore,
    PresentationOutputStoreError,
    StoredPresentationOutput,
)


class PresentationOutputError(RuntimeError):
    pass


@dataclass(frozen=True)
class PresentationOutputSnapshot:
    asset_id: UUID
    task_id: UUID
    sha256: str
    byte_size: int
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
    plan_checksum: str
    renderer_version: str
    template_code: str
    template_version: str
    slide_count: int
    created: bool
    completed: PresentationOutputSnapshot | None
    renderer_result: dict | None


class PresentationOutputService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        renderer_client,
        output_store: PresentationOutputStore,
    ) -> None:
        self._session_factory = session_factory
        self._renderer = renderer_client
        self._outputs = output_store

    async def render(
        self, task_id: UUID, step_id: UUID, plan
    ) -> PresentationOutputSnapshot:
        validated = PresentationPlan.validate_for_renderer(plan)
        plan_payload = validated.model_dump(mode="json", exclude_none=True)
        plan_checksum = presentation_plan_sha256(validated)
        pending = await self._prepare(task_id, step_id, validated, plan_checksum)
        if pending.completed is not None:
            stored = self._outputs.inspect(pending.user_id, pending.asset_id)
            if (
                stored is None
                or stored.sha256 != pending.completed.sha256
                or stored.byte_size != pending.completed.byte_size
            ):
                raise PresentationOutputError("presentation_output_integrity_failed")
            return pending.completed

        stored = self._recover_stored_output(pending)
        if stored is None:
            await self._mark_renderer_started(pending)
            rendered = await self._renderer.render(pending.asset_id, plan_payload)
            renderer_result = self._renderer_result(rendered)
            self._verify_renderer_result(pending, renderer_result)
            await self._record_renderer_result(pending, rendered)
            stored = self._persist_or_recover(pending, rendered)
        else:
            renderer_result = pending.renderer_result
            if renderer_result is None:
                raise PresentationOutputError("presentation_checkpoint_invalid")
            self._verify_renderer_result(pending, renderer_result)
        return await self._finalize(
            pending,
            stored,
            renderer_result,
            replayed=not pending.created,
        )

    async def _mark_renderer_started(self, pending: _PendingOutput) -> None:
        async with self._session_factory() as session, session.begin():
            step = await session.get(
                GenerationTaskStep, pending.step_id, with_for_update=True
            )
            asset = await session.get(FileAsset, pending.asset_id, with_for_update=True)
            if step is None or asset is None or asset.processing_status != "parsing":
                raise PresentationOutputError("presentation_checkpoint_missing")
            checkpoint = dict(step.checkpoint or {})
            if checkpoint.get("presentation_plan_checksum") != pending.plan_checksum:
                raise PresentationOutputError("presentation_plan_conflict")
            checkpoint["renderer_call_started"] = True
            step.checkpoint = checkpoint

    async def _prepare(
        self,
        task_id: UUID,
        step_id: UUID,
        plan: PresentationPlan,
        plan_checksum: str,
    ) -> _PendingOutput:
        async with self._session_factory() as session, session.begin():
            task = await session.get(GenerationTask, task_id, with_for_update=True)
            step = await session.get(GenerationTaskStep, step_id, with_for_update=True)
            if (
                task is None
                or step is None
                or step.task_id != task.id
                or step.output_kind != "pptx"
                or step.step_key != "render:pptx"
            ):
                raise PresentationOutputError("presentation_step_invalid")
            template_input = await session.scalar(
                select(GenerationTaskInput).where(
                    GenerationTaskInput.task_id == task.id,
                    GenerationTaskInput.input_type == "template",
                    GenerationTaskInput.reference_key
                    == f"{plan.template.code}@{plan.template.version}",
                )
            )
            frozen_outputs = [
                item for item in task.skill_snapshot if item.get("kind") == "pptx"
            ]
            if (
                template_input is None
                or len(frozen_outputs) != 1
                or frozen_outputs[0].get("template_code") != plan.template.code
                or frozen_outputs[0].get("template_version") != plan.template.version
            ):
                raise PresentationOutputError("presentation_template_conflict")
            idempotency_key = self._idempotency_key(step.id, task.retry_count)
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
                raise PresentationOutputError("presentation_step_invalid")
            if asset is None:
                asset_id = new_uuid7()
                asset = FileAsset(
                    id=asset_id,
                    user_id=task.user_id,
                    project_id=task.project_id,
                    original_filename="sales-presentation.pptx",
                    file_category="presentation",
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "presentationml.presentation"
                    ),
                    byte_size=0,
                    sha256="0" * 64,
                    storage_provider="local",
                    storage_key=self._outputs.build_key(task.user_id, asset_id),
                    processing_status="parsing",
                    idempotency_key=idempotency_key,
                    generated_task_id=task.id,
                    processing_warnings=[],
                    parser_name="pptxgenjs",
                    parser_version=plan.renderer_version,
                    processing_started_at=utc_now(),
                )
                session.add(asset)
            checkpoint = dict(step.checkpoint or {})
            existing_checksum = checkpoint.get("presentation_plan_checksum")
            if existing_checksum is not None and existing_checksum != plan_checksum:
                raise PresentationOutputError("presentation_plan_conflict")
            checkpoint.update(
                {
                    "provider_call_started": False,
                    "renderer_call_started": checkpoint.get(
                        "renderer_call_started", False
                    ),
                    "output_asset_id": str(asset.id),
                    "presentation_plan_checksum": plan_checksum,
                    "renderer_version": plan.renderer_version,
                    "template_code": plan.template.code,
                    "template_version": plan.template.version,
                    "slide_count": len(plan.slides),
                }
            )
            step.checkpoint = checkpoint
            await session.flush()
            if asset.processing_status == "ready":
                return _PendingOutput(
                    asset_id=asset.id,
                    user_id=asset.user_id,
                    task_id=task.id,
                    step_id=step.id,
                    plan_checksum=plan_checksum,
                    renderer_version=plan.renderer_version,
                    template_code=plan.template.code,
                    template_version=plan.template.version,
                    slide_count=len(plan.slides),
                    created=False,
                    completed=self._snapshot(asset, checkpoint, replayed=True),
                    renderer_result=None,
                )
            if asset.processing_status != "parsing":
                raise PresentationOutputError("presentation_output_state_invalid")
            return _PendingOutput(
                asset_id=asset.id,
                user_id=asset.user_id,
                task_id=task.id,
                step_id=step.id,
                plan_checksum=plan_checksum,
                renderer_version=plan.renderer_version,
                template_code=plan.template.code,
                template_version=plan.template.version,
                slide_count=len(plan.slides),
                created=created,
                completed=None,
                renderer_result=checkpoint.get("renderer_result"),
            )

    async def _record_renderer_result(
        self, pending: _PendingOutput, rendered: RenderedPresentation
    ) -> None:
        result = self._renderer_result(rendered)
        async with self._session_factory() as session, session.begin():
            step = await session.get(
                GenerationTaskStep, pending.step_id, with_for_update=True
            )
            asset = await session.get(FileAsset, pending.asset_id, with_for_update=True)
            if step is None or asset is None or asset.processing_status != "parsing":
                raise PresentationOutputError("presentation_checkpoint_missing")
            checkpoint = dict(step.checkpoint or {})
            if checkpoint.get("presentation_plan_checksum") != pending.plan_checksum:
                raise PresentationOutputError("presentation_plan_conflict")
            checkpoint["renderer_call_completed"] = True
            checkpoint["renderer_result"] = result
            step.checkpoint = checkpoint

    def _recover_stored_output(
        self, pending: _PendingOutput
    ) -> StoredPresentationOutput | None:
        if pending.renderer_result is None:
            return None
        stored = self._outputs.inspect(pending.user_id, pending.asset_id)
        if stored is None:
            return None
        self._verify_stored(stored, pending.renderer_result)
        return stored

    def _persist_or_recover(
        self, pending: _PendingOutput, rendered: RenderedPresentation
    ) -> StoredPresentationOutput:
        existing = self._outputs.inspect(pending.user_id, pending.asset_id)
        if existing is not None:
            self._verify_stored(existing, self._renderer_result(rendered))
            return existing
        try:
            stored = self._outputs.persist(
                pending.user_id, pending.asset_id, rendered.path
            )
        except PresentationOutputStoreError:
            existing = self._outputs.inspect(pending.user_id, pending.asset_id)
            if existing is None:
                raise
            stored = existing
        self._verify_stored(stored, self._renderer_result(rendered))
        return stored

    async def _finalize(
        self,
        pending: _PendingOutput,
        stored: StoredPresentationOutput,
        renderer_result: dict,
        *,
        replayed: bool,
    ) -> PresentationOutputSnapshot:
        self._verify_stored(stored, renderer_result)
        async with self._session_factory() as session, session.begin():
            asset = await session.get(FileAsset, pending.asset_id, with_for_update=True)
            step = await session.get(
                GenerationTaskStep, pending.step_id, with_for_update=True
            )
            if asset is None or step is None:
                raise PresentationOutputError("presentation_checkpoint_missing")
            if asset.processing_status == "ready":
                return self._snapshot(asset, dict(step.checkpoint), replayed=True)
            if (
                asset.processing_status != "parsing"
                or asset.generated_task_id != pending.task_id
                or asset.storage_key != stored.storage_key
            ):
                raise PresentationOutputError("presentation_output_state_invalid")
            asset.byte_size = stored.byte_size
            asset.sha256 = stored.sha256
            asset.processing_status = "ready"
            asset.processed_at = utc_now()
            checkpoint = dict(step.checkpoint or {})
            checkpoint["renderer_call_completed"] = True
            checkpoint["renderer_result"] = renderer_result
            step.checkpoint = checkpoint
            await session.flush()
            return self._snapshot(asset, checkpoint, replayed=replayed)

    @staticmethod
    def _verify_stored(stored: StoredPresentationOutput, result: dict) -> None:
        if stored.sha256 != result.get("sha256") or stored.byte_size != result.get(
            "byte_size"
        ):
            raise PresentationOutputError("presentation_output_integrity_failed")

    @staticmethod
    def _verify_renderer_result(pending: _PendingOutput, result: dict) -> None:
        if (
            result.get("plan_sha256") != pending.plan_checksum
            or result.get("renderer_version") != pending.renderer_version
            or result.get("template_code") != pending.template_code
            or result.get("template_version") != pending.template_version
            or result.get("slide_count") != pending.slide_count
        ):
            raise PresentationOutputError("presentation_renderer_result_invalid")

    @staticmethod
    def _renderer_result(rendered: RenderedPresentation) -> dict:
        return {
            "sha256": rendered.sha256,
            "byte_size": rendered.byte_size,
            "slide_count": rendered.slide_count,
            "template_code": rendered.template_code,
            "template_version": rendered.template_version,
            "renderer_version": rendered.renderer_version,
            "plan_sha256": rendered.plan_sha256,
        }

    @staticmethod
    def _idempotency_key(step_id: UUID, retry_count: int = 0) -> str:
        base_key = f"render-output:{step_id}"
        return base_key if retry_count == 0 else f"{base_key}:retry:{retry_count}"

    @staticmethod
    def _snapshot(
        asset: FileAsset, checkpoint: dict, *, replayed: bool
    ) -> PresentationOutputSnapshot:
        required = {
            "renderer_version",
            "template_code",
            "template_version",
        }
        if asset.generated_task_id is None or not required.issubset(checkpoint):
            raise PresentationOutputError("presentation_checkpoint_invalid")
        return PresentationOutputSnapshot(
            asset_id=asset.id,
            task_id=asset.generated_task_id,
            sha256=asset.sha256,
            byte_size=asset.byte_size,
            renderer_version=checkpoint["renderer_version"],
            template_code=checkpoint["template_code"],
            template_version=checkpoint["template_version"],
            replayed=replayed,
        )
