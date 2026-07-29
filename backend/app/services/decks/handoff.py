from hashlib import sha256
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.briefs import Brief
from app.models.deck_draft_inputs import DeckDraftInput
from app.models.deck_draft_revisions import DeckDraftRevision
from app.models.deck_drafts import DeckDraft
from app.models.workflow_tasks import WorkflowTask
from app.services.auth_sessions import AuthSessionService, CurrentUser
from app.services.briefs.contracts import StructuredBrief
from app.services.decks.contracts import (
    DeckBrief,
    DeckConfirmCommand,
    DeckDraftSnapshot,
    DeckGenerationCommand,
    DeckOperationError,
    deck_content_checksum,
)
from app.services.decks.media_inputs import build_deck_media_inputs
from app.services.preflight.contracts import PreflightCommand
from app.services.preflight.service import BriefWorkflowService
from app.templates.catalog import get_presentation_template


class DeckHandoffService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
        brief_workflow: BriefWorkflowService | None,
        generation,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions
        self._brief_workflow = brief_workflow
        self._generation = generation

    async def confirm(
        self,
        access_token: str,
        draft_id: UUID,
        command: DeckConfirmCommand,
    ) -> DeckDraftSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session, session.begin():
            draft = await self._owned_draft(
                session, current_user, draft_id, for_update=True
            )
            if draft.latest_revision != command.expected_revision:
                raise DeckOperationError(
                    "deck_revision_stale",
                    "Deck Revision 已更新，请刷新后重试",
                    409,
                )
            row = await self._revision(session, draft, draft.latest_revision)
            content = self._validated_revision(row)
            if (
                row.high_risk_confirmation_required
                and not command.high_risk_confirmed
                and row.high_risk_confirmed_at is None
            ):
                raise DeckOperationError(
                    "high_risk_confirmation_required",
                    "高风险内容需要显式确认后继续",
                    409,
                )
            if row.bridge_brief_id is None:
                bridge = await self._build_bridge(session, draft, row, content)
                row.bridge_brief_id = bridge.id
                session.add(self._workflow_task(draft, row, content, bridge))
            if row.high_risk_confirmation_required:
                from app.models.base import utc_now

                row.high_risk_confirmed_at = utc_now()
            if row.status not in {"ready", "generation_queued"}:
                from app.models.base import utc_now

                row.status = "confirmed"
                row.confirmed_at = row.confirmed_at or utc_now()
                draft.status = "confirmed"
            await session.flush()
            return self._snapshot(draft, row)

    async def preflight(
        self,
        access_token: str,
        draft_id: UUID,
    ) -> DeckDraftSnapshot:
        if self._brief_workflow is None:
            raise DeckOperationError(
                "deck_preflight_not_configured", "Deck Preflight 未配置", 503
            )
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            draft = await self._owned_draft(session, current_user, draft_id)
            row = await self._revision(session, draft, draft.latest_revision)
            if row.bridge_brief_id is None or row.status not in {
                "confirmed",
                "needs_resolution",
                "ready",
            }:
                raise DeckOperationError(
                    "deck_revision_not_confirmed",
                    "请先确认最新 Deck Revision",
                    409,
                )
            bridge_brief_id = row.bridge_brief_id
            revision_id = row.id
        snapshot = await self._brief_workflow.preflight(
            access_token,
            PreflightCommand(brief_id=bridge_brief_id),
        )
        async with self._session_factory() as session, session.begin():
            draft = await self._owned_draft(
                session, current_user, draft_id, for_update=True
            )
            row = await session.get(
                DeckDraftRevision, revision_id, with_for_update=True
            )
            if row is None or draft.latest_revision != row.revision:
                raise DeckOperationError(
                    "deck_revision_stale",
                    "Deck Revision 已更新，请刷新后重试",
                    409,
                )
            row.preflight_snapshot = snapshot.model_dump(mode="json")
            row.status = "needs_resolution" if snapshot.has_blockers else "ready"
            draft.status = row.status
            workflow = await session.scalar(
                select(WorkflowTask).where(
                    WorkflowTask.brief_group_id == draft.draft_group_id
                )
            )
            if workflow is not None:
                workflow.stage = (
                    "deck_needs_resolution" if snapshot.has_blockers else "deck_ready"
                )
                workflow.status = (
                    "needs_resolution"
                    if snapshot.has_blockers
                    else "awaiting_confirmation"
                )
                workflow.progress = 25
                workflow.note = (
                    "请处理 Deck Preflight 阻断项"
                    if snapshot.has_blockers
                    else "Deck 已通过预检，可确认生成"
                )
            await session.flush()
            return self._snapshot(draft, row)

    async def generate(
        self,
        access_token: str,
        draft_id: UUID,
        command: DeckGenerationCommand,
        idempotency_key: str,
    ):
        if self._brief_workflow is None or self._generation is None:
            raise DeckOperationError(
                "deck_generation_not_configured", "Deck Generation 未配置", 503
            )
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            draft = await self._owned_draft(session, current_user, draft_id)
            if draft.latest_revision != command.expected_revision:
                raise DeckOperationError(
                    "deck_revision_stale",
                    "Deck Revision 已更新，请刷新后重试",
                    409,
                )
            row = await self._revision(session, draft, draft.latest_revision)
            if row.status not in {"ready", "generation_queued"}:
                raise DeckOperationError(
                    "deck_preflight_blocked",
                    "Deck 尚未通过 Preflight",
                    409,
                )
            if (
                row.preflight_snapshot is None
                or row.preflight_snapshot.get("has_blockers") is not False
                or row.preflight_snapshot.get("estimated_credits")
                != command.accepted_estimated_credits
                or row.bridge_brief_id is None
            ):
                raise DeckOperationError(
                    "deck_preflight_stale",
                    "Deck Preflight 或预计积分已变化",
                    409,
                )
            bridge_brief_id = row.bridge_brief_id
            revision_id = row.id
            media_inputs = await self._media_inputs(session, draft, row)
        await self._brief_workflow.confirm(
            access_token,
            bridge_brief_id,
            accepted_estimated_credits=command.accepted_estimated_credits,
        )
        generation = await self._generation.create(
            access_token,
            bridge_brief_id,
            idempotency_key,
            additional_inputs=media_inputs,
        )
        async with self._session_factory() as session, session.begin():
            draft = await self._owned_draft(
                session, current_user, draft_id, for_update=True
            )
            row = await session.get(
                DeckDraftRevision, revision_id, with_for_update=True
            )
            if row is None or draft.latest_revision != row.revision:
                raise DeckOperationError(
                    "deck_revision_stale",
                    "Deck Revision 已更新，请刷新后重试",
                    409,
                )
            row.generation_task_id = generation.task_id
            row.status = "generation_queued"
            draft.status = "generation_queued"
        return generation

    @staticmethod
    async def _media_inputs(
        session: AsyncSession,
        draft: DeckDraft,
        row: DeckDraftRevision,
    ) -> tuple[dict, ...]:
        return await build_deck_media_inputs(session, draft, row)

    @staticmethod
    async def _image_inputs(
        session: AsyncSession,
        draft: DeckDraft,
        row: DeckDraftRevision,
    ) -> tuple[dict, ...]:
        return await build_deck_media_inputs(session, draft, row)

    async def _build_bridge(
        self,
        session: AsyncSession,
        draft: DeckDraft,
        row: DeckDraftRevision,
        content: DeckBrief,
    ) -> Brief:
        inputs = list(
            await session.scalars(
                select(DeckDraftInput).where(DeckDraftInput.revision_id == row.id)
            )
        )
        source_assets = [
            {
                "asset_id": str(item.source_asset_id),
                "asset_version": item.source_version,
            }
            for item in inputs
            if item.source_asset_id is not None
        ]
        selected_model = {
            key: row.model_snapshot[key]
            for key in ("model_id", "provider_id", "credential_id", "model_code")
        }
        template_snapshot = row.template_snapshot or {}
        template_code = template_snapshot.get("template_code")
        template_version = template_snapshot.get("version")
        template_checksum = template_snapshot.get("checksum")
        template = (
            get_presentation_template(template_code, template_version)
            if isinstance(template_code, str) and isinstance(template_version, str)
            else None
        )
        if (
            template is None
            or template.checksum != template_checksum
            or content.skill_code not in template.compatible_skills
        ):
            raise DeckOperationError(
                "template_contract_invalid",
                "系统模板版本合同不可用",
                409,
            )
        selected_skill = {
            "skill_code": content.skill_code,
            "version": row.skill_snapshot["version"],
        }
        must_include = []
        for slide in content.slides:
            evidence_ids = tuple(
                evidence_id
                for provenance in slide.provenance
                for evidence_id in provenance.evidence_ids
            )
            must_include.append(
                {
                    "content": f"{slide.title}：{'；'.join(slide.body)}"[:512],
                    "source": "file" if evidence_ids else "agnes_inference",
                    "evidence_ids": evidence_ids[:8],
                }
            )
        structured = StructuredBrief.model_validate(
            {
                "module": "ppt",
                "goal": content.topic,
                "audience": content.audience,
                "language": "zh-CN",
                "domain": "general",
                "tone": "professional",
                "source_asset_versions": source_assets,
                "term_library_versions": [],
                "selected_skills": [selected_skill],
                "selected_model": selected_model,
                "output_plan": {
                    "deliverables": [
                        {
                            "kind": "pptx",
                            "title": content.topic,
                            "source": "user",
                            "evidence_ids": [],
                        }
                    ]
                },
                "facts": [
                    {
                        "content": content.topic,
                        "source": "user",
                        "evidence_ids": [],
                    }
                ],
                "inferences": [],
                "unresolved_items": [],
                "must_include": must_include,
                "must_exclude": [],
                "citation_policy": {
                    "internal_tracking": True,
                    "visible_citations": False,
                },
            }
        )
        payload = structured.model_dump(mode="json")
        bridge = Brief(
            brief_group_id=draft.draft_group_id,
            revision=row.revision,
            user_id=draft.user_id,
            project_id=draft.project_id,
            selected_model_id=UUID(selected_model["model_id"]),
            source_snapshot={
                "deck_revision_id": str(row.id),
                "source_asset_versions": source_assets,
                "term_library_versions": [],
                "selected_skills": [selected_skill],
                "selected_model": selected_model,
                "template_versions": [
                    {
                        "template_code": template_code,
                        "version": template_version,
                        "checksum": template_checksum,
                    }
                ],
                "resolutions": [],
            },
            content=payload,
            content_checksum=self._checksum(payload),
            status="draft",
        )
        session.add(bridge)
        await session.flush()
        return bridge

    @staticmethod
    def _workflow_task(
        draft: DeckDraft,
        row: DeckDraftRevision,
        content: DeckBrief,
        bridge: Brief,
    ) -> WorkflowTask:
        return WorkflowTask(
            user_id=draft.user_id,
            project_id=draft.project_id,
            brief_group_id=bridge.brief_group_id,
            generation_task_id=None,
            idempotency_key=f"deck-workflow:{row.id}",
            title=content.topic,
            request_snapshot={
                "schema_version": "deck-workflow-reference.v1",
                "deck_draft_id": str(draft.id),
                "deck_revision_id": str(row.id),
            },
            output_kinds=["pptx"],
            stage="deck_confirmed",
            status="awaiting_confirmation",
            progress=20,
            note="Deck 已确认，等待 Preflight",
            failure_code=None,
            failure_reason=None,
            dispatch_sequence=1,
        )

    @staticmethod
    async def _owned_draft(
        session: AsyncSession,
        current_user: CurrentUser,
        draft_id: UUID,
        *,
        for_update: bool = False,
    ) -> DeckDraft:
        statement = select(DeckDraft).where(
            DeckDraft.id == draft_id,
            DeckDraft.user_id == current_user.user_id,
            DeckDraft.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        draft = await session.scalar(statement)
        if draft is None:
            raise DeckOperationError("deck_draft_not_found", "Deck Draft 不存在", 404)
        return draft

    @staticmethod
    async def _revision(
        session: AsyncSession, draft: DeckDraft, revision: int
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
    def _validated_revision(row: DeckDraftRevision) -> DeckBrief:
        try:
            content = DeckBrief.model_validate(row.content)
        except Exception as exception:
            raise DeckOperationError(
                "deck_integrity_failed", "Deck 内容完整性校验失败", 409
            ) from exception
        if deck_content_checksum(content) != row.content_checksum:
            raise DeckOperationError(
                "deck_integrity_failed", "Deck 内容完整性校验失败", 409
            )
        return content

    @classmethod
    def _snapshot(cls, draft: DeckDraft, row: DeckDraftRevision) -> DeckDraftSnapshot:
        return DeckDraftSnapshot(
            draft_id=draft.id,
            thread_id=draft.thread_id,
            source_message_id=draft.source_message_id,
            revision_id=row.id,
            revision=row.revision,
            status=row.status,
            content=cls._validated_revision(row),
            content_checksum=row.content_checksum,
            template_snapshot=row.template_snapshot,
            preflight_snapshot=row.preflight_snapshot,
            generation_task_id=row.generation_task_id,
            confirmed_at=row.confirmed_at,
        )

    @staticmethod
    def _checksum(payload: dict) -> str:
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return sha256(canonical.encode("utf-8")).hexdigest()
