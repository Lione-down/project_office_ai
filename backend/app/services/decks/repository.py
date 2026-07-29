from hashlib import sha256
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.chat_messages import ChatMessage
from app.models.chat_threads import ChatThread
from app.models.deck_draft_inputs import DeckDraftInput
from app.models.deck_draft_revisions import DeckDraftRevision
from app.models.deck_drafts import DeckDraft
from app.models.file_assets import FileAsset
from app.models.projects import Project
from app.models.provider_calls import ProviderCall
from app.models.provider_credentials import ProviderCredential
from app.models.skills import Skill
from app.services.auth_sessions import CurrentUser
from app.services.decks.contracts import (
    DeckBrief,
    DeckCreateCommand,
    DeckDraftSnapshot,
    DeckOperationError,
    deck_content_checksum,
)
from app.skills.catalog import (
    POST_ALPHA_USER_SKILLS,
    skill_row_matches_definition,
)


class DeckRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def load_create_inputs(
        self,
        current_user: CurrentUser,
        message_id: UUID,
        command: DeckCreateCommand,
    ):
        async with self._session_factory() as session:
            message = await session.scalar(
                select(ChatMessage)
                .join(ChatThread, ChatThread.id == ChatMessage.thread_id)
                .where(
                    ChatMessage.id == message_id,
                    ChatMessage.role == "assistant",
                    ChatMessage.status == "succeeded",
                    ChatThread.user_id == current_user.user_id,
                    ChatThread.deleted_at.is_(None),
                )
            )
            if message is None:
                raise DeckOperationError(
                    "chat_message_not_found", "Chat 消息不存在", 404
                )
            project = await session.scalar(
                select(Project).where(
                    Project.id == command.project_id,
                    Project.user_id == current_user.user_id,
                    Project.deleted_at.is_(None),
                )
            )
            if project is None:
                raise DeckOperationError("project_not_found", "项目不存在", 404)
            model = await session.get(AiModel, command.model_id)
            provider = (
                await session.get(AiProvider, model.provider_id)
                if model is not None
                else None
            )
            credential = (
                await session.get(ProviderCredential, model.credential_id)
                if model is not None
                else None
            )
            expected_skill = next(
                (
                    item
                    for item in POST_ALPHA_USER_SKILLS
                    if item.skill_code == command.skill_code
                ),
                None,
            )
            skill = await session.scalar(
                select(Skill).where(
                    Skill.skill_code == command.skill_code,
                    Skill.version == "1.0.0",
                    Skill.status == "published",
                )
            )
            if (
                model is None
                or provider is None
                or credential is None
                or model.status != "active"
                or not model.user_visible
                or provider.vendor != "agnes"
                or provider.status != "active"
                or credential.status != "active"
                or command.skill_code not in set(model.allowed_skills or [])
                or model.capabilities.get("text_generation") is not True
                or model.capabilities.get("structured_output") is not True
            ):
                raise DeckOperationError(
                    "model_capability_mismatch",
                    "所选模型当前不满足 Deck Skill 能力要求",
                    422,
                )
            if (
                expected_skill is None
                or skill is None
                or not skill_row_matches_definition(skill, expected_skill)
            ):
                raise DeckOperationError(
                    "skill_contract_invalid", "Deck Skill 版本合同不可用", 409
                )
            assets = ()
            if command.asset_ids:
                rows = list(
                    await session.scalars(
                        select(FileAsset).where(
                            FileAsset.id.in_(command.asset_ids),
                            FileAsset.user_id == current_user.user_id,
                            FileAsset.project_id == command.project_id,
                            FileAsset.deleted_at.is_(None),
                        )
                    )
                )
                rows_by_id = {row.id: row for row in rows}
                assets = tuple(
                    rows_by_id.get(asset_id) for asset_id in command.asset_ids
                )
                if (
                    any(asset is None for asset in assets)
                    or any(
                        asset.processing_status != "ready"
                        or asset.manifest_status != "valid"
                        or not asset.manifest_key
                        or not asset.manifest_sha256
                        for asset in assets
                        if asset is not None
                    )
                    or sum(asset.byte_size for asset in assets if asset is not None)
                    > 200 * 1024 * 1024
                ):
                    raise DeckOperationError(
                        "deck_evidence_invalid",
                        "Deck 来源材料不可用",
                        422,
                    )
            return message, model, provider, credential, skill, assets

    async def persist_created(
        self,
        *,
        current_user,
        message,
        command,
        idempotency_key,
        fingerprint,
        draft_group_id,
        content,
        model,
        provider,
        credential,
        skill,
        assets,
    ) -> DeckDraftSnapshot:
        try:
            async with self._session_factory() as session, session.begin():
                draft = DeckDraft(
                    user_id=current_user.user_id,
                    project_id=command.project_id,
                    thread_id=message.thread_id,
                    source_message_id=message.id,
                    draft_group_id=draft_group_id,
                    latest_revision=1,
                    status="draft",
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                )
                session.add(draft)
                await session.flush()
                row = DeckDraftRevision(
                    draft_id=draft.id,
                    revision=1,
                    content=content.model_dump(mode="json"),
                    content_checksum=deck_content_checksum(content),
                    source_mode=content.source_mode,
                    skill_snapshot={
                        "skill_code": skill.skill_code,
                        "version": skill.version,
                        "checksum": skill.checksum,
                    },
                    model_snapshot={
                        "model_id": str(model.id),
                        "provider_id": str(provider.id),
                        "credential_id": str(credential.id),
                        "model_code": model.model_code,
                        "credit_multiplier": str(model.credit_multiplier),
                    },
                    template_snapshot=None,
                    provenance_summary=self._provenance_summary(content),
                    preflight_snapshot=None,
                    high_risk_confirmation_required=self._is_high_risk(content),
                    high_risk_confirmed_at=None,
                    status="draft",
                )
                session.add(row)
                await session.flush()
                session.add_all(
                    [
                        DeckDraftInput(
                            revision_id=row.id,
                            input_kind="message",
                            source_asset_id=None,
                            source_message_id=message.id,
                            source_version="chat-message.v1",
                            source_checksum=sha256(
                                message.content.encode("utf-8")
                            ).hexdigest(),
                            evidence_snapshot={},
                            provenance_kind="agnes_inference",
                        ),
                        *[
                            DeckDraftInput(
                                revision_id=row.id,
                                input_kind="asset",
                                source_asset_id=asset.id,
                                source_message_id=None,
                                source_version=f"sha256:{asset.sha256}",
                                source_checksum=asset.sha256,
                                evidence_snapshot={
                                    "manifest_schema_version": (
                                        asset.manifest_schema_version
                                    ),
                                    "manifest_sha256": asset.manifest_sha256,
                                    "evidence_engine_version": (
                                        asset.evidence_engine_version
                                    ),
                                },
                                provenance_kind="source_evidence",
                            )
                            for asset in assets
                        ],
                    ]
                )
                await session.flush()
                return self._snapshot(draft, row)
        except IntegrityError:
            existing = await self.existing_by_key(
                current_user.user_id, idempotency_key, fingerprint
            )
            if existing is None:
                existing = await self.existing_by_source(
                    current_user.user_id,
                    message.id,
                    fingerprint,
                )
            if existing is None:
                raise
            return existing

    async def record_provider_call(
        self,
        group_id,
        attempt,
        provider,
        model,
        credential,
        completion,
        latency_ms,
        status,
        error_category,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                ProviderCall(
                    brief_group_id=group_id,
                    attempt=attempt,
                    provider_id=provider.id,
                    model_id=model.id,
                    credential_id=credential.id,
                    provider_request_id=(
                        completion.provider_request_id if completion else None
                    ),
                    status=status,
                    prompt_tokens=completion.usage.prompt_tokens if completion else 0,
                    completion_tokens=(
                        completion.usage.completion_tokens if completion else 0
                    ),
                    total_tokens=completion.usage.total_tokens if completion else 0,
                    latency_ms=latency_ms,
                    error_category=error_category,
                    is_redacted=True,
                )
            )

    async def existing_by_key(
        self, user_id: UUID, key: str, fingerprint: str
    ) -> DeckDraftSnapshot | None:
        async with self._session_factory() as session:
            draft = await session.scalar(
                select(DeckDraft).where(
                    DeckDraft.user_id == user_id,
                    DeckDraft.idempotency_key == key,
                )
            )
            if draft is None:
                return None
            if draft.request_fingerprint != fingerprint:
                raise DeckOperationError(
                    "idempotency_conflict",
                    "Idempotency-Key 已用于不同请求",
                    409,
                )
            row = await self._revision(session, draft, draft.latest_revision)
            return self._snapshot(draft, row, replayed=True)

    async def existing_by_source(
        self,
        user_id: UUID,
        message_id: UUID,
        fingerprint: str,
    ) -> DeckDraftSnapshot | None:
        async with self._session_factory() as session:
            draft = await session.scalar(
                select(DeckDraft).where(
                    DeckDraft.user_id == user_id,
                    DeckDraft.source_message_id == message_id,
                    DeckDraft.deleted_at.is_(None),
                )
            )
            if draft is None:
                return None
            if draft.request_fingerprint != fingerprint:
                raise DeckOperationError(
                    "deck_source_already_converted",
                    "该 assistant message 已有 Deck Draft，请编辑已有 Draft",
                    409,
                )
            row = await self._revision(session, draft, draft.latest_revision)
            return self._snapshot(draft, row, replayed=True)

    @staticmethod
    async def _revision(
        session: AsyncSession,
        draft: DeckDraft,
        revision: int,
    ) -> DeckDraftRevision:
        row = await session.scalar(
            select(DeckDraftRevision).where(
                DeckDraftRevision.draft_id == draft.id,
                DeckDraftRevision.revision == revision,
            )
        )
        if row is None:
            raise DeckOperationError("deck_draft_not_found", "Deck Draft 不存在", 404)
        return row

    @staticmethod
    def _snapshot(
        draft: DeckDraft,
        row: DeckDraftRevision,
        *,
        replayed: bool = False,
    ) -> DeckDraftSnapshot:
        content = DeckBrief.model_validate(row.content)
        return DeckDraftSnapshot(
            draft_id=draft.id,
            thread_id=draft.thread_id,
            source_message_id=draft.source_message_id,
            revision_id=row.id,
            revision=row.revision,
            status=row.status,
            content=content,
            content_checksum=row.content_checksum,
            preflight_snapshot=row.preflight_snapshot,
            generation_task_id=row.generation_task_id,
            confirmed_at=row.confirmed_at,
            replayed=replayed,
        )

    @staticmethod
    def _provenance_summary(content: DeckBrief) -> dict:
        counts = {"user_input": 0, "agnes_inference": 0, "source_evidence": 0}
        evidence_ids = []
        for slide in content.slides:
            for item in slide.provenance:
                counts[item.kind] += 1
                evidence_ids.extend(item.evidence_ids)
        return {
            "counts": counts,
            "evidence_ids": list(dict.fromkeys(evidence_ids)),
        }

    @staticmethod
    def _is_high_risk(content: DeckBrief) -> bool:
        haystack = " ".join(
            [
                content.topic,
                content.audience,
                *[
                    text
                    for slide in content.slides
                    for text in (slide.title, slide.purpose, *slide.body)
                ],
            ]
        )
        return bool(
            re.search(
                r"(医学|医疗|诊断|用药|法律|诉讼|投资|证券|金融建议)",
                haystack,
            )
        )
