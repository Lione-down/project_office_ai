from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.base import utc_now
from app.models.file_assets import FileAsset
from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.services.generation_worker import StepExecutionResult
from app.services.quality.presentation.artifact_store import (
    PresentationQualityArtifactStore,
    StoredQualityReport,
)
from app.services.quality.presentation.contracts import (
    LibreOfficeVerification,
    PresentationPreviewReference,
    PresentationQualityFinding,
    PresentationQualityReport,
    PresentationValidatedOutputReference,
)
from app.services.quality.presentation.libreoffice import (
    LibreOfficeConversion,
    LibreOfficeError,
)
from app.services.quality.presentation.service_helpers import (
    blocker,
    file_digest,
    request_id,
    ensure_report_matches,
    required,
    source_reference,
    validated_key,
)
from app.services.renderers.presentation.contracts import (
    PresentationPlan,
    presentation_plan_sha256,
)
from app.storage.local import LocalStorageAdapter


class PresentationQualityError(RuntimeError):
    pass


@dataclass(frozen=True)
class PresentationQualityOutcome:
    report: PresentationQualityReport
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
            "presentation_quality_blocked",
            **common,
        )


@dataclass(frozen=True)
class _PendingQuality:
    asset_id: UUID
    user_id: UUID
    task_id: UUID
    step_id: UUID
    storage_key: str
    source_sha256: str
    source_byte_size: int
    slide_count: int
    renderer_version: str
    template_code: str
    template_version: str
    plan_sha256: str
    replay_report_key: str | None
    replay_report_sha256: str | None
    replay_validated_key: str | None


class PresentationQualityService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: LocalStorageAdapter,
        artifacts: PresentationQualityArtifactStore,
        inspector,
        repairer,
        libreoffice,
        *,
        temp_root: str | Path,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._artifacts = artifacts
        self._inspector = inspector
        self._repairer = repairer
        self._libreoffice = libreoffice
        self._temp_root = Path(temp_root).resolve()

    async def evaluate(
        self, asset_id: UUID, step_id: UUID, plan_value
    ) -> PresentationQualityOutcome:
        plan = PresentationPlan.validate_for_renderer(plan_value)
        plan_sha256 = presentation_plan_sha256(plan)
        pending = await self._prepare(asset_id, step_id, plan, plan_sha256)
        if pending.replay_report_key is not None:
            return self._replay(pending, plan)
        recovered = self._artifacts.recover_report(pending.user_id, pending.asset_id)
        if recovered is not None:
            report, stored_report = recovered
            ensure_report_matches(pending, plan, report, PresentationQualityError)
            self._artifacts.verify_report_artifacts(
                pending.user_id, pending.asset_id, report
            )
            recovered_validated_key = validated_key(pending, report)
            if report.download_allowed:
                self._verify_validated_artifact(
                    pending, report, recovered_validated_key
                )
            return await self._finalize(
                pending,
                report,
                stored_report,
                validated_key=recovered_validated_key,
                replayed=True,
            )
        return await self._run_quality_gate(pending, plan)

    async def _run_quality_gate(
        self, pending: _PendingQuality, plan: PresentationPlan
    ) -> PresentationQualityOutcome:
        source_path = self._storage.resolve_asset_key(
            pending.user_id, pending.asset_id, pending.storage_key
        )
        initial = self._inspector.inspect(
            source_path,
            expected_slide_count=pending.slide_count,
            expected_evidence_ids=set(plan.evidence_ids),
        )
        findings = list(initial.findings)
        repair_warnings: list[PresentationQualityFinding] = []
        repair_attempt_count = 0
        repaired_sha256: str | None = None
        validated_path = source_path
        validated_key = pending.storage_key
        validated_sha256 = pending.source_sha256
        validated_byte_size = pending.source_byte_size
        source_variant = "original"
        blockers = [finding for finding in findings if finding.severity == "blocker"]
        if blockers and all(finding.repairable for finding in blockers):
            repair_attempt_count = 1
            self._temp_root.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(
                prefix="presentation-quality-", dir=self._temp_root
            ) as temporary:
                repaired = self._repairer.repair(
                    source_path,
                    Path(temporary) / "repaired.pptx",
                    tuple(findings),
                )
                staged = self._artifacts.stage_repaired(
                    pending.user_id, pending.asset_id, repaired.path
                )
            validated_path = staged.path
            validated_key = staged.key
            validated_sha256 = staged.sha256
            validated_byte_size = staged.byte_size
            repaired_sha256 = staged.sha256
            source_variant = "repaired"
            repair_warnings = list(repaired.warnings)
            findings = list(
                self._inspector.inspect(
                    validated_path,
                    expected_slide_count=pending.slide_count,
                    expected_evidence_ids=set(plan.evidence_ids),
                ).findings
            )
        conversion: LibreOfficeConversion | None = None
        libreoffice_result: LibreOfficeVerification
        if any(finding.severity == "blocker" for finding in findings):
            libreoffice_result = LibreOfficeVerification(
                status="failed",
                error_code="quality_precheck_blocked",
            )
        else:
            try:
                conversion = await self._libreoffice.convert(
                    request_id=request_id(pending.asset_id, validated_sha256),
                    user_id=pending.user_id,
                    asset_id=pending.asset_id,
                    source_sha256=validated_sha256,
                    source_byte_size=validated_byte_size,
                    source_variant=source_variant,
                )
            except LibreOfficeError as exception:
                code = (
                    "libreoffice_unavailable"
                    if exception.retryable
                    else "libreoffice_open_failed"
                )
                findings.append(blocker(code, "presentation-libreoffice.v1"))
                libreoffice_result = LibreOfficeVerification(
                    status="unavailable" if exception.retryable else "failed",
                    error_code=code,
                )
            else:
                libreoffice_result = LibreOfficeVerification(
                    status="passed",
                    version=conversion.libreoffice_version,
                    pdf_sha256=conversion.pdf.sha256,
                    pdf_byte_size=conversion.pdf.byte_size,
                    page_count=len(conversion.pages),
                )
                if len(conversion.pages) != pending.slide_count:
                    findings.append(
                        blocker(
                            "libreoffice_page_count_mismatch",
                            "presentation-libreoffice.v1",
                        )
                    )
        final_findings = [*repair_warnings, *findings]
        has_blocker = any(finding.severity == "blocker" for finding in final_findings)
        status = (
            "blocked"
            if has_blocker
            else "passed_with_warnings"
            if repair_warnings
            else "passed"
        )
        previews = (
            [
                PresentationPreviewReference(
                    page_number=page.page_number,
                    sha256=required(page.sha256),
                    byte_size=required(page.byte_size),
                    width=page.width,
                    height=page.height,
                )
                for page in conversion.pages
            ]
            if conversion is not None
            else []
        )
        report = PresentationQualityReport(
            schema_version="presentation-quality-report.v1",
            quality_engine_version="presentation-quality.v1",
            source=source_reference(pending),
            validated_output=PresentationValidatedOutputReference(
                asset_id=pending.asset_id,
                sha256=validated_sha256,
                byte_size=validated_byte_size,
            ),
            status=status,
            download_allowed=not has_blocker,
            findings=final_findings,
            libreoffice=libreoffice_result,
            previews=previews,
            repair_attempt_count=repair_attempt_count,
            repaired_output_sha256=repaired_sha256,
            generated_at=utc_now(),
        )
        stored_report = self._artifacts.persist_report(
            pending.user_id,
            pending.asset_id,
            report,
            conversion=conversion,
        )
        return await self._finalize(
            pending,
            report,
            stored_report,
            validated_key=validated_key if report.download_allowed else None,
            replayed=False,
        )

    async def _prepare(
        self,
        asset_id: UUID,
        step_id: UUID,
        plan: PresentationPlan,
        plan_sha256: str,
    ) -> _PendingQuality:
        async with self._session_factory() as session, session.begin():
            asset = await session.get(FileAsset, asset_id, with_for_update=True)
            step = await session.get(GenerationTaskStep, step_id, with_for_update=True)
            task = (
                await session.get(GenerationTask, step.task_id, with_for_update=True)
                if step is not None
                else None
            )
            if (
                asset is None
                or step is None
                or task is None
                or asset.generated_task_id != task.id
                or step.task_id != task.id
                or step.step_key != "render:pptx"
                or step.output_kind != "pptx"
                or asset.processing_status != "ready"
            ):
                raise PresentationQualityError("presentation_quality_input_invalid")
            checkpoint = dict(step.checkpoint or {})
            renderer_result = checkpoint.get("renderer_result")
            if (
                not isinstance(renderer_result, dict)
                or checkpoint.get("output_asset_id") != str(asset.id)
                or checkpoint.get("presentation_plan_checksum") != plan_sha256
                or checkpoint.get("renderer_version") != plan.renderer_version
                or checkpoint.get("template_code") != plan.template.code
                or checkpoint.get("template_version") != plan.template.version
                or checkpoint.get("slide_count") != len(plan.slides)
                or renderer_result.get("sha256") != asset.sha256
                or renderer_result.get("byte_size") != asset.byte_size
                or renderer_result.get("plan_sha256") != plan_sha256
            ):
                raise PresentationQualityError(
                    "presentation_quality_input_integrity_failed"
                )
            if asset.quality_status is None:
                if task.status != "running" or step.status != "running":
                    raise PresentationQualityError("presentation_quality_step_invalid")
                checkpoint["quality_gate_started"] = True
                checkpoint["quality_engine_version"] = "presentation-quality.v1"
                step.checkpoint = checkpoint
            return _PendingQuality(
                asset_id=asset.id,
                user_id=asset.user_id,
                task_id=task.id,
                step_id=step.id,
                storage_key=asset.storage_key,
                source_sha256=asset.sha256,
                source_byte_size=asset.byte_size,
                slide_count=len(plan.slides),
                renderer_version=plan.renderer_version,
                template_code=plan.template.code,
                template_version=plan.template.version,
                plan_sha256=plan_sha256,
                replay_report_key=asset.quality_report_key,
                replay_report_sha256=asset.quality_report_sha256,
                replay_validated_key=asset.quality_validated_key,
            )

    def _replay(
        self, pending: _PendingQuality, plan: PresentationPlan
    ) -> PresentationQualityOutcome:
        if pending.replay_report_key is None or pending.replay_report_sha256 is None:
            raise PresentationQualityError("presentation_quality_state_invalid")
        report = self._artifacts.load_report(
            pending.user_id,
            pending.asset_id,
            pending.replay_report_key,
            pending.replay_report_sha256,
        )
        ensure_report_matches(pending, plan, report, PresentationQualityError)
        try:
            self._artifacts.verify_report_artifacts(
                pending.user_id, pending.asset_id, report
            )
        except Exception as exception:
            raise PresentationQualityError(
                "presentation_quality_preview_integrity_failed"
            ) from exception
        validated_key = pending.replay_validated_key
        if report.download_allowed:
            self._verify_validated_artifact(pending, report, validated_key)
        elif validated_key is not None:
            raise PresentationQualityError("presentation_quality_state_invalid")
        return PresentationQualityOutcome(
            report=report,
            report_key=pending.replay_report_key,
            report_sha256=pending.replay_report_sha256,
            validated_key=validated_key,
            replayed=True,
        )

    async def _finalize(
        self,
        pending: _PendingQuality,
        report: PresentationQualityReport,
        stored_report: StoredQualityReport,
        *,
        validated_key: str | None,
        replayed: bool,
    ) -> PresentationQualityOutcome:
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
                raise PresentationQualityError("presentation_quality_source_changed")
            if asset.quality_status is not None:
                if (
                    asset.quality_status != report.status
                    or asset.quality_report_key != stored_report.report_key
                    or asset.quality_report_sha256 != stored_report.report_sha256
                    or asset.quality_validated_key != validated_key
                ):
                    raise PresentationQualityError(
                        "presentation_quality_state_conflict"
                    )
                return PresentationQualityOutcome(
                    report=report,
                    report_key=stored_report.report_key,
                    report_sha256=stored_report.report_sha256,
                    validated_key=validated_key,
                    replayed=True,
                )
            asset.quality_status = report.status
            asset.quality_report_key = stored_report.report_key
            asset.quality_report_sha256 = stored_report.report_sha256
            asset.quality_report_schema_version = report.schema_version
            asset.quality_engine_version = report.quality_engine_version
            asset.quality_preview_keys = list(stored_report.preview_keys)
            asset.quality_validated_key = validated_key
            asset.quality_validated_sha256 = (
                report.validated_output.sha256 if report.download_allowed else None
            )
            asset.quality_validated_byte_size = (
                report.validated_output.byte_size if report.download_allowed else None
            )
            asset.quality_repair_attempt_count = report.repair_attempt_count
            asset.quality_checked_at = report.generated_at
            checkpoint = dict(step.checkpoint or {})
            checkpoint.update(
                {
                    "quality_gate_completed": True,
                    "quality_status": report.status,
                    "quality_report_schema_version": report.schema_version,
                    "quality_report_sha256": stored_report.report_sha256,
                    "quality_engine_version": report.quality_engine_version,
                    "quality_repair_attempt_count": report.repair_attempt_count,
                    "quality_download_allowed": report.download_allowed,
                    "asset_version": f"sha256:{asset.sha256}",
                }
            )
            step.checkpoint = checkpoint
        return PresentationQualityOutcome(
            report=report,
            report_key=stored_report.report_key,
            report_sha256=stored_report.report_sha256,
            validated_key=validated_key,
            replayed=replayed,
        )

    def _verify_validated_artifact(
        self,
        pending: _PendingQuality,
        report: PresentationQualityReport,
        validated_key: str | None,
    ) -> None:
        if validated_key == pending.storage_key:
            path = self._storage.resolve_asset_key(
                pending.user_id, pending.asset_id, validated_key
            )
            digest, byte_size = file_digest(path)
        elif validated_key is not None:
            artifact = self._artifacts.resolve_repaired(
                pending.user_id, pending.asset_id, validated_key
            )
            digest, byte_size = artifact.sha256, artifact.byte_size
        else:
            raise PresentationQualityError("presentation_quality_state_invalid")
        if (
            digest != report.validated_output.sha256
            or byte_size != report.validated_output.byte_size
        ):
            raise PresentationQualityError(
                "presentation_quality_output_integrity_failed"
            )
