from dataclasses import replace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.briefs import Brief
from app.models.file_assets import FileAsset
from app.models.provider_credentials import ProviderCredential
from app.models.skills import Skill
from app.services.auth_sessions import CurrentUser
from app.services.briefs.contracts import StructuredBrief
from app.services.evidence.contracts import EvidenceItem, EvidenceProcessingError
from app.services.evidence.store import EvidenceManifestStore
from app.services.preflight.catalog import (
    TemplateSelectionError,
    build_alpha_output_plan,
)
from app.services.preflight.contracts import (
    ConflictFinding,
    PlannedOutputSnapshot,
    PreflightSnapshot,
)
from app.skills.catalog import (
    ALPHA_SKILLS,
    SkillSelectionError,
    resolve_alpha_skill_selection,
    skill_row_matches_definition,
)


RESOLVABLE_BRIEF_BLOCKERS = frozenset(
    {
        "unit_unknown",
        "numeric_low_confidence",
        "source_conflict",
        "metric_scope_conflict",
    }
)


class PreflightEvaluator:
    def __init__(self, manifest_store: EvidenceManifestStore) -> None:
        self._manifest_store = manifest_store

    async def evaluate(
        self,
        session: AsyncSession,
        current_user: CurrentUser,
        brief: Brief,
        *,
        content: StructuredBrief,
    ) -> PreflightSnapshot:
        referenced_evidence_ids = _referenced_evidence_ids(content)
        evidence, manifest_findings = await self._load_evidence(
            session,
            current_user,
            brief,
            referenced_evidence_ids=referenced_evidence_ids,
        )
        findings = [
            *manifest_findings,
            *self._evidence_findings(evidence),
            *self._brief_findings(content, brief.source_snapshot),
        ]
        model = await session.get(AiModel, brief.selected_model_id)
        findings.extend(await self._compatibility_findings(session, content, model))
        outputs = ()
        estimated_credits = 0
        if model is not None:
            try:
                outputs = self.build_outputs(content, brief.source_snapshot, model)
                estimated_credits = sum(item.estimated_credits for item in outputs)
            except TemplateSelectionError as exception:
                findings.append(
                    ConflictFinding(
                        code=exception.error_code,
                        level="incompatible",
                        message=exception.message,
                    )
                )
        resolution_keys = {
            (_canonical_conflict_code(item["code"]), tuple(item["evidence_ids"]))
            for item in brief.source_snapshot.get("resolutions", [])
        }
        findings = [
            finding
            for finding in findings
            if (finding.code, finding.evidence_ids) not in resolution_keys
        ]
        findings = _deduplicate_findings(findings)
        has_blockers = any(
            finding.level in {"blocking", "incompatible"} for finding in findings
        )
        return PreflightSnapshot(
            brief_id=brief.id,
            brief_group_id=brief.brief_group_id,
            revision=brief.revision,
            status="needs_resolution" if has_blockers else "preflight",
            conflicts=tuple(findings),
            outputs=tuple(PlannedOutputSnapshot(**item.__dict__) for item in outputs),
            credit_multiplier=model.credit_multiplier if model is not None else None,
            estimated_credits=estimated_credits,
            has_blockers=has_blockers,
        )

    async def _load_evidence(
        self,
        session: AsyncSession,
        current_user: CurrentUser,
        brief: Brief,
        *,
        referenced_evidence_ids: frozenset[str],
    ) -> tuple[tuple[EvidenceItem, ...], list[ConflictFinding]]:
        evidence = []
        findings = []
        for reference in brief.source_snapshot.get("source_asset_versions", []):
            asset_id = UUID(str(reference["asset_id"]))
            asset = await session.scalar(
                select(FileAsset).where(
                    FileAsset.id == asset_id,
                    FileAsset.user_id == current_user.user_id,
                    FileAsset.project_id == brief.project_id,
                    FileAsset.deleted_at.is_(None),
                )
            )
            if (
                asset is None
                or asset.processing_status != "ready"
                or asset.manifest_status != "valid"
                or f"sha256:{asset.sha256}" != reference["asset_version"]
                or not asset.manifest_key
                or not asset.manifest_sha256
            ):
                findings.append(_source_unavailable())
                continue
            try:
                manifest = self._manifest_store.read(
                    current_user.user_id,
                    asset.id,
                    asset.manifest_key,
                    expected_sha256=asset.manifest_sha256,
                )
            except EvidenceProcessingError:
                findings.append(_source_unavailable())
                continue
            referenced_evidence = tuple(
                item
                for item in manifest.evidence
                if item.evidence_id in referenced_evidence_ids
            )
            evidence.extend(referenced_evidence)
            evidence_by_id = {item.evidence_id: item for item in referenced_evidence}
            findings.extend(
                ConflictFinding(
                    code=_canonical_conflict_code(issue.code),
                    level="blocking",
                    message=_evidence_conflict_message(
                        _canonical_conflict_code(issue.code),
                        evidence_by_id[issue.evidence_id],
                    ),
                    evidence_ids=(issue.evidence_id,),
                )
                for issue in manifest.blockers
                if issue.evidence_id in evidence_by_id
            )
        return tuple(evidence), findings

    @staticmethod
    def _evidence_findings(evidence: tuple[EvidenceItem, ...]) -> list[ConflictFinding]:
        findings = []
        for item in evidence:
            if item.value_kind != "number":
                continue
            warning_codes = set(item.warnings)
            if (
                item.unit is None
                or {"unit_unknown", "numeric_unit_unknown"} & warning_codes
            ):
                findings.append(
                    ConflictFinding(
                        code="unit_unknown",
                        level="blocking",
                        message=_evidence_conflict_message("unit_unknown", item),
                        evidence_ids=(item.evidence_id,),
                    )
                )
            if item.ocr_confidence is not None and item.ocr_confidence < 0.90:
                findings.append(
                    ConflictFinding(
                        code="numeric_low_confidence",
                        level="blocking",
                        message=_evidence_conflict_message(
                            "numeric_low_confidence", item
                        ),
                        evidence_ids=(item.evidence_id,),
                    )
                )
        return findings

    @staticmethod
    def _brief_findings(
        content: StructuredBrief, source_snapshot: dict
    ) -> list[ConflictFinding]:
        resolutions = {
            (_canonical_conflict_code(item["code"]), tuple(item["evidence_ids"]))
            for item in source_snapshot.get("resolutions", [])
        }
        findings = []
        for item in content.unresolved_items:
            code = _canonical_conflict_code(item.code)
            if (code, item.evidence_ids) in resolutions:
                continue
            findings.append(
                ConflictFinding(
                    code=code,
                    level=(
                        "blocking"
                        if item.blocking and code in RESOLVABLE_BRIEF_BLOCKERS
                        else "needs_confirmation"
                    ),
                    message=(
                        _conflict_message(code)
                        if item.blocking and code in RESOLVABLE_BRIEF_BLOCKERS
                        else f"请确认：{item.content}"
                    ),
                    evidence_ids=item.evidence_ids,
                )
            )
        return findings

    @staticmethod
    async def _compatibility_findings(
        session: AsyncSession,
        content: StructuredBrief,
        model: AiModel | None,
    ) -> list[ConflictFinding]:
        findings = []
        try:
            selection = resolve_alpha_skill_selection(
                tuple(item.skill_code for item in content.selected_skills)
            )
        except SkillSelectionError as exception:
            return [
                ConflictFinding(
                    code=exception.error_code,
                    level="incompatible",
                    message=exception.message,
                )
            ]
        if selection.module == "combined":
            findings.append(
                ConflictFinding(
                    code="skill_inputs_shared",
                    level="auto_merge",
                    message="PPTX 与 XLSX 将共享材料、术语库和所选模型",
                )
            )
        expected_by_code = {skill.skill_code: skill for skill in ALPHA_SKILLS}
        rows = list(
            await session.scalars(
                select(Skill).where(
                    Skill.skill_code.in_(
                        [skill.skill_code for skill in selection.skills]
                    ),
                    Skill.version == "1.0.0",
                )
            )
        )
        rows_by_code = {row.skill_code: row for row in rows}
        if any(
            (row := rows_by_code.get(skill.skill_code)) is None
            or not skill_row_matches_definition(row, expected_by_code[skill.skill_code])
            for skill in selection.skills
        ):
            findings.append(
                ConflictFinding(
                    code="skill_contract_invalid",
                    level="incompatible",
                    message="所选 Skill 版本合同不可用，请重新选择",
                )
            )
        selected_codes = {item.skill_code for item in content.selected_skills}
        capabilities = model.capabilities if model is not None else {}
        credential = (
            await session.get(ProviderCredential, model.credential_id)
            if model is not None
            else None
        )
        provider = (
            await session.get(AiProvider, model.provider_id)
            if model is not None
            else None
        )
        if (
            model is None
            or model.id != content.selected_model.model_id
            or model.provider_id != content.selected_model.provider_id
            or model.credential_id != content.selected_model.credential_id
            or model.model_code != content.selected_model.model_code
            or model.status != "active"
            or not model.user_visible
            or provider is None
            or provider.vendor != "agnes"
            or provider.status != "active"
            or credential is None
            or credential.provider_id != model.provider_id
            or credential.status != "active"
            or not selected_codes.issubset(set(model.allowed_skills or []))
            or capabilities.get("text_generation") is not True
            or capabilities.get("structured_output") is not True
        ):
            findings.append(
                ConflictFinding(
                    code="model_capability_mismatch",
                    level="incompatible",
                    message="所选模型当前不满足 Skill 能力要求，请更换模型",
                )
            )
        return findings

    @staticmethod
    def build_outputs(content: StructuredBrief, source_snapshot: dict, model: AiModel):
        template_versions = tuple(
            (item["template_code"], item["version"])
            for item in source_snapshot.get("template_versions", [])
        )
        outputs = build_alpha_output_plan(
            tuple(item.skill_code for item in content.selected_skills),
            template_versions,
            model.credit_multiplier,
        )
        titles = {item.kind: item.title for item in content.output_plan.deliverables}
        return tuple(
            replace(output, title=titles.get(output.kind, output.title))
            for output in outputs
        )


def _source_unavailable() -> ConflictFinding:
    return ConflictFinding(
        code="source_snapshot_unavailable",
        level="blocking",
        message="请重新处理已变化或不可用的来源材料",
    )


def _conflict_message(code: str) -> str:
    return {
        "unit_unknown": "请为数值补充明确单位后继续",
        "numeric_unit_unknown": "请为数值补充明确单位后继续",
        "numeric_low_confidence": "请核对低置信度数字并确认后继续",
        "ocr_numeric_low_confidence": "请核对低置信度数字并确认后继续",
        "source_conflict": "请选择权威来源后继续",
        "metric_scope_conflict": "请选择明确的数据口径后继续",
    }.get(code, "请处理当前阻断项后继续")


def _canonical_conflict_code(code: str) -> str:
    return {
        "numeric_unit_unknown": "unit_unknown",
        "ocr_numeric_low_confidence": "numeric_low_confidence",
    }.get(code, code)


def _evidence_conflict_message(code: str, item: EvidenceItem) -> str:
    location = item.location
    if location.kind == "excel_cell":
        label = f"工作表“{location.sheet}”单元格 {location.cell}"
    elif location.kind == "csv_cell":
        label = f"表格第 {location.row} 行、第 {location.column} 列"
    elif location.kind == "pdf_region":
        label = f"PDF 第 {location.page} 页"
    elif location.kind == "word_paragraph":
        label = f"Word 第 {location.paragraph} 段"
    elif location.kind == "text_line":
        label = f"文本第 {location.line} 行"
    else:
        label = "图片识别区域"
    return f"{label}：{_conflict_message(code)}"


def _referenced_evidence_ids(content: StructuredBrief) -> frozenset[str]:
    collections = (
        content.facts,
        content.inferences,
        content.output_plan.deliverables,
        content.unresolved_items,
        content.must_include,
        content.must_exclude,
    )
    return frozenset(
        evidence_id
        for items in collections
        for item in items
        for evidence_id in item.evidence_ids
    )


def _deduplicate_findings(
    findings: list[ConflictFinding],
) -> list[ConflictFinding]:
    deduplicated = {}
    for finding in findings:
        deduplicated[(finding.code, finding.level, finding.evidence_ids)] = finding
    return list(deduplicated.values())
