from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.file_assets import FileAsset
from app.models.projects import Project
from app.models.provider_credentials import ProviderCredential
from app.models.skills import Skill
from app.models.term_items import TermItem
from app.models.term_libraries import TermLibrary
from app.services.auth_sessions import CurrentUser
from app.services.briefs.contracts import BriefGenerationCommand
from app.services.briefs.errors import BriefOperationError
from app.services.briefs.validation import ExpectedBriefSnapshot
from app.services.evidence.contracts import EvidenceItem, EvidenceProcessingError
from app.services.evidence.store import EvidenceManifestStore
from app.services.terminology.contracts import TermRule
from app.skills.catalog import (
    ALPHA_SKILLS,
    SkillSelection,
    skill_row_matches_definition,
)


@dataclass(frozen=True)
class GenerationInputs:
    current_user: CurrentUser
    project: Project
    assets: tuple[FileAsset, ...]
    term_versions: tuple[TermLibrary, ...]
    term_rules: tuple[TermRule, ...]
    selection: SkillSelection
    model: AiModel
    provider: AiProvider
    credential: ProviderCredential
    evidence: tuple[EvidenceItem, ...]


class GenerationInputLoader:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        manifest_store: EvidenceManifestStore,
    ) -> None:
        self._session_factory = session_factory
        self._manifest_store = manifest_store

    async def load(
        self,
        current_user: CurrentUser,
        command: BriefGenerationCommand,
        selection: SkillSelection,
    ) -> GenerationInputs:
        async with self._session_factory() as session:
            project = await session.scalar(
                select(Project).where(
                    Project.id == command.project_id,
                    Project.user_id == current_user.user_id,
                    Project.deleted_at.is_(None),
                )
            )
            if project is None:
                raise BriefOperationError("project_not_found", "项目不存在", 404)
            await self._validate_skill_rows(session, selection)
            loaded_assets, loaded_evidence = await self._load_assets(
                session, current_user, project, command
            )
            terms, term_rules = await self._load_terms(
                session, current_user, project, command
            )
            model = await session.get(AiModel, command.model_id)
            if model is None:
                raise BriefOperationError("model_not_found", "模型不存在", 404)
            provider = await session.get(AiProvider, model.provider_id)
            credential = await session.get(ProviderCredential, model.credential_id)
            self._validate_model(selection, model, provider, credential)
            return GenerationInputs(
                current_user=current_user,
                project=project,
                assets=loaded_assets,
                term_versions=terms,
                term_rules=term_rules,
                selection=selection,
                model=model,
                provider=provider,
                credential=credential,
                evidence=loaded_evidence,
            )

    async def _load_assets(
        self,
        session: AsyncSession,
        current_user: CurrentUser,
        project: Project,
        command: BriefGenerationCommand,
    ) -> tuple[tuple[FileAsset, ...], tuple[EvidenceItem, ...]]:
        assets = []
        evidence = []
        for asset_id in command.asset_ids:
            asset = await session.scalar(
                select(FileAsset).where(
                    FileAsset.id == asset_id,
                    FileAsset.user_id == current_user.user_id,
                    FileAsset.project_id == project.id,
                    FileAsset.deleted_at.is_(None),
                )
            )
            if asset is None:
                raise BriefOperationError("asset_not_found", "资产不存在", 404)
            if (
                asset.processing_status != "ready"
                or asset.manifest_status != "ready"
                or not asset.manifest_key
                or not asset.manifest_sha256
            ):
                raise BriefOperationError(
                    "asset_not_ready", "资产 Evidence 尚未就绪", 409
                )
            try:
                manifest = self._manifest_store.read(
                    current_user.user_id,
                    asset.id,
                    asset.manifest_key,
                    expected_sha256=asset.manifest_sha256,
                )
            except EvidenceProcessingError as exception:
                raise BriefOperationError(
                    exception.error_code, exception.safe_message, 409
                ) from exception
            if manifest.asset_version != f"sha256:{asset.sha256}":
                raise BriefOperationError(
                    "evidence_manifest_integrity_failed",
                    "Evidence Manifest 资产版本不一致",
                    409,
                )
            assets.append(asset)
            evidence.extend(manifest.evidence)
        return tuple(assets), tuple(evidence)

    @staticmethod
    async def _load_terms(
        session: AsyncSession,
        current_user: CurrentUser,
        project: Project,
        command: BriefGenerationCommand,
    ) -> tuple[tuple[TermLibrary, ...], tuple[TermRule, ...]]:
        terms = []
        rules = []
        for reference in command.term_library_versions:
            term = await session.scalar(
                select(TermLibrary).where(
                    TermLibrary.library_id == reference.library_id,
                    TermLibrary.version == reference.version,
                    TermLibrary.user_id == current_user.user_id,
                    TermLibrary.status == "active",
                )
            )
            if term is None or term.project_id not in (None, project.id):
                raise BriefOperationError("term_library_not_found", "术语库不存在", 404)
            terms.append(term)
            items = list(
                await session.scalars(
                    select(TermItem)
                    .where(TermItem.term_library_version_id == term.id)
                    .order_by(TermItem.priority.desc(), TermItem.item_id)
                )
            )
            rules.extend(
                TermRule(
                    library_id=term.library_id,
                    library_version=term.version,
                    project_id=term.project_id,
                    canonical_term=item.canonical_term,
                    aliases=tuple(item.aliases),
                    unit=item.unit,
                    metric_scope=item.metric_scope,
                    priority=item.priority,
                )
                for item in items
            )
        return tuple(terms), tuple(rules)

    @staticmethod
    async def _validate_skill_rows(
        session: AsyncSession, selection: SkillSelection
    ) -> None:
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
        for selected in selection.skills:
            row = rows_by_code.get(selected.skill_code)
            expected = expected_by_code[selected.skill_code]
            if row is None or not skill_row_matches_definition(row, expected):
                raise BriefOperationError(
                    "skill_contract_invalid", "Skill版本合同不可用", 409
                )

    @staticmethod
    def _validate_model(
        selection: SkillSelection,
        model: AiModel,
        provider: AiProvider | None,
        credential: ProviderCredential | None,
    ) -> None:
        selected_codes = {skill.skill_code for skill in selection.skills}
        capabilities = model.capabilities or {}
        if (
            provider is None
            or credential is None
            or provider.vendor != "agnes"
            or provider.status != "active"
            or credential.provider_id != provider.id
            or credential.status != "active"
            or model.provider_id != provider.id
            or model.credential_id != credential.id
            or model.status != "active"
            or not model.user_visible
            or not selected_codes.issubset(set(model.allowed_skills or []))
            or capabilities.get("text_generation") is not True
            or capabilities.get("structured_output") is not True
        ):
            raise BriefOperationError(
                "model_capability_mismatch",
                "模型不满足所选 Skill 能力要求",
                422,
            )


def expected_snapshot(
    inputs: GenerationInputs, command: BriefGenerationCommand
) -> ExpectedBriefSnapshot:
    return ExpectedBriefSnapshot(
        module=inputs.selection.module,
        goal=command.goal,
        audience=command.audience,
        must_include=command.must_include,
        must_exclude=command.must_exclude,
        source_asset_versions=tuple(
            (asset.id, f"sha256:{asset.sha256}") for asset in inputs.assets
        ),
        term_library_versions=tuple(
            (term.library_id, term.version) for term in inputs.term_versions
        ),
        selected_skills=tuple(
            (skill.skill_code, skill.version) for skill in inputs.selection.skills
        ),
        model_id=inputs.model.id,
        provider_id=inputs.provider.id,
        credential_id=inputs.credential.id,
        model_code=inputs.model.model_code,
        evidence_ids=frozenset(item.evidence_id for item in inputs.evidence),
    )
