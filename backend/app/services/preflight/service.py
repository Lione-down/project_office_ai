from hashlib import sha256
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_models import AiModel
from app.models.briefs import Brief
from app.models.base import utc_now
from app.services.auth_sessions import AuthSessionService, CurrentUser
from app.services.briefs.contracts import BriefContentItem, StructuredBrief
from app.services.briefs.errors import BriefOperationError
from app.services.evidence.store import EvidenceManifestStore
from app.services.preflight.contracts import (
    BriefRevisionCommand,
    BriefSnapshot,
    PreflightCommand,
    PreflightSnapshot,
)
from app.services.preflight.evaluator import PreflightEvaluator


class BriefWorkflowService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
        manifest_store: EvidenceManifestStore,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions
        self._evaluator = PreflightEvaluator(manifest_store)

    async def get(self, access_token: str, brief_id: UUID) -> BriefSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            brief = await self._owned_brief(session, current_user, brief_id)
            return self._brief_snapshot(brief)

    async def revise(
        self,
        access_token: str,
        brief_id: UUID,
        command: BriefRevisionCommand,
    ) -> BriefSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session, session.begin():
            current = await self._owned_brief(
                session, current_user, brief_id, for_update=True
            )
            latest = await self._latest_revision(
                session, current_user, current.brief_group_id, for_update=True
            )
            if latest.id != current.id or latest.revision != command.expected_revision:
                raise BriefOperationError(
                    "brief_revision_stale", "Brief Revision 已更新，请刷新后重试", 409
                )
            if latest.status == "queued":
                raise BriefOperationError(
                    "brief_already_confirmed", "已确认 Brief 不可修改", 409
                )
            content = self._revised_content(latest, command)
            source_snapshot = dict(latest.source_snapshot)
            source_snapshot.update(
                {
                    "goal": content.goal,
                    "audience": content.audience,
                    "must_include": [
                        item.model_dump(mode="json") for item in content.must_include
                    ],
                    "must_exclude": [
                        item.model_dump(mode="json") for item in content.must_exclude
                    ],
                }
            )
            if command.template_versions is not None:
                source_snapshot["template_versions"] = [
                    item.model_dump(mode="json") for item in command.template_versions
                ]
            if command.resolutions is not None:
                current_preflight = await self._evaluator.evaluate(
                    session,
                    current_user,
                    latest,
                    content=self._validated_content(latest),
                )
                self._validate_resolutions(current_preflight, command)
                resolutions = {
                    (item["code"], tuple(item["evidence_ids"])): dict(item)
                    for item in source_snapshot.get("resolutions", [])
                }
                resolutions.update(
                    {
                        (item.code, item.evidence_ids): item.model_dump(mode="json")
                        for item in command.resolutions
                    }
                )
                source_snapshot["resolutions"] = list(resolutions.values())
            model = await session.get(AiModel, latest.selected_model_id)
            if model is None:
                raise BriefOperationError("model_not_found", "模型不存在", 404)
            self._evaluator.build_outputs(content, source_snapshot, model)
            payload = content.model_dump(mode="json")
            revision = Brief(
                brief_group_id=latest.brief_group_id,
                revision=latest.revision + 1,
                user_id=latest.user_id,
                project_id=latest.project_id,
                selected_model_id=latest.selected_model_id,
                source_snapshot=source_snapshot,
                content=payload,
                content_checksum=_content_checksum(payload),
                status="draft",
                preflight_snapshot=None,
                estimated_credits=None,
                confirmed_at=None,
            )
            session.add(revision)
            await session.flush()
            return self._brief_snapshot(revision)

    async def preflight(
        self, access_token: str, command: PreflightCommand
    ) -> PreflightSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        deferred_error = None
        result = None
        async with self._session_factory() as session, session.begin():
            brief = await self._owned_brief(
                session, current_user, command.brief_id, for_update=True
            )
            if brief.status == "queued":
                return self._confirmed_snapshot(brief)
            await self._require_latest(session, current_user, brief)
            snapshot = await self._evaluate(session, current_user, brief)
            if command.one_click and not snapshot.has_blockers:
                if command.accepted_estimated_credits != snapshot.estimated_credits:
                    deferred_error = BriefOperationError(
                        "estimated_credits_changed", "预计积分已变化，请重新确认", 409
                    )
                else:
                    result = self._queue(brief, snapshot)
            if result is None:
                brief.status = snapshot.status
                brief.preflight_snapshot = snapshot.model_dump(mode="json")
                result = snapshot
        if deferred_error is not None:
            raise deferred_error
        return result

    async def confirm(
        self,
        access_token: str,
        brief_id: UUID,
        *,
        accepted_estimated_credits: int,
    ) -> PreflightSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        deferred_error = None
        result = None
        async with self._session_factory() as session, session.begin():
            brief = await self._owned_brief(
                session, current_user, brief_id, for_update=True
            )
            if brief.status == "queued":
                if brief.estimated_credits != accepted_estimated_credits:
                    raise BriefOperationError(
                        "estimated_credits_changed", "预计积分与已确认快照不一致", 409
                    )
                return self._confirmed_snapshot(brief)
            await self._require_latest(session, current_user, brief)
            snapshot = await self._evaluate(session, current_user, brief)
            if snapshot.has_blockers:
                brief.status = "needs_resolution"
                brief.preflight_snapshot = snapshot.model_dump(mode="json")
                deferred_error = BriefOperationError(
                    "preflight_blocked", "仍有阻断项，无法确认 Brief", 409
                )
                result = snapshot
            elif accepted_estimated_credits != snapshot.estimated_credits:
                brief.status = "preflight"
                brief.preflight_snapshot = snapshot.model_dump(mode="json")
                deferred_error = BriefOperationError(
                    "estimated_credits_changed", "预计积分已变化，请重新确认", 409
                )
                result = snapshot
            else:
                result = self._queue(brief, snapshot)
        if deferred_error is not None:
            raise deferred_error
        return result

    async def _evaluate(
        self, session: AsyncSession, current_user: CurrentUser, brief: Brief
    ) -> PreflightSnapshot:
        return await self._evaluator.evaluate(
            session,
            current_user,
            brief,
            content=self._validated_content(brief),
        )

    @staticmethod
    def _revised_content(
        brief: Brief, command: BriefRevisionCommand
    ) -> StructuredBrief:
        content = BriefWorkflowService._validated_content(brief)
        updates = {}
        if command.goal is not None:
            updates["goal"] = command.goal
        if command.audience is not None:
            updates["audience"] = command.audience
        if command.must_include is not None:
            updates["must_include"] = tuple(
                BriefContentItem(content=value, source="user", evidence_ids=())
                for value in command.must_include
            )
        if command.must_exclude is not None:
            updates["must_exclude"] = tuple(
                BriefContentItem(content=value, source="user", evidence_ids=())
                for value in command.must_exclude
            )
        if command.output_titles:
            titles = {item.kind: item.title for item in command.output_titles}
            updates["output_plan"] = content.output_plan.model_copy(
                update={
                    "deliverables": tuple(
                        item.model_copy(
                            update={"title": titles.get(item.kind, item.title)}
                        )
                        for item in content.output_plan.deliverables
                    )
                }
            )
        if command.visible_citations is not None:
            updates["citation_policy"] = content.citation_policy.model_copy(
                update={"visible_citations": command.visible_citations}
            )
        return StructuredBrief.model_validate(
            content.model_copy(update=updates).model_dump(mode="json")
        )

    @staticmethod
    def _validate_resolutions(
        preflight: PreflightSnapshot, command: BriefRevisionCommand
    ) -> None:
        unresolved = {
            (item.code, item.evidence_ids)
            for item in preflight.conflicts
            if item.level in {"blocking", "incompatible"}
        }
        if any(
            (item.code, item.evidence_ids) not in unresolved
            for item in command.resolutions or ()
        ):
            raise BriefOperationError(
                "resolution_invalid", "冲突处理未匹配当前 Brief 阻断项", 422
            )

    @staticmethod
    def _validated_content(brief: Brief) -> StructuredBrief:
        try:
            content = StructuredBrief.model_validate(brief.content)
        except Exception as exception:
            raise BriefOperationError(
                "brief_integrity_failed", "Brief 内容完整性校验失败", 409
            ) from exception
        if _content_checksum(content.model_dump(mode="json")) != brief.content_checksum:
            raise BriefOperationError(
                "brief_integrity_failed", "Brief 内容完整性校验失败", 409
            )
        return content

    @staticmethod
    async def _owned_brief(
        session: AsyncSession,
        current_user: CurrentUser,
        brief_id: UUID,
        *,
        for_update: bool = False,
    ) -> Brief:
        statement = select(Brief).where(
            Brief.id == brief_id, Brief.user_id == current_user.user_id
        )
        if for_update:
            statement = statement.with_for_update()
        brief = await session.scalar(statement)
        if brief is None:
            raise BriefOperationError("brief_not_found", "Brief 不存在", 404)
        return brief

    @staticmethod
    async def _latest_revision(
        session: AsyncSession,
        current_user: CurrentUser,
        brief_group_id: UUID,
        *,
        for_update: bool = False,
    ) -> Brief:
        statement = (
            select(Brief)
            .where(
                Brief.brief_group_id == brief_group_id,
                Brief.user_id == current_user.user_id,
            )
            .order_by(Brief.revision.desc())
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def _require_latest(
        self, session: AsyncSession, current_user: CurrentUser, brief: Brief
    ) -> None:
        latest = await self._latest_revision(
            session, current_user, brief.brief_group_id, for_update=True
        )
        if latest.id != brief.id:
            raise BriefOperationError(
                "brief_revision_stale", "Brief Revision 已更新，请刷新后重试", 409
            )

    @staticmethod
    def _queue(
        brief: Brief,
        snapshot: PreflightSnapshot,
    ) -> PreflightSnapshot:
        confirmed_at = utc_now()
        confirmed = snapshot.model_copy(
            update={"status": "queued", "confirmed_at": confirmed_at}
        )
        brief.status = "queued"
        brief.preflight_snapshot = confirmed.model_dump(mode="json")
        brief.estimated_credits = snapshot.estimated_credits
        brief.confirmed_at = confirmed_at
        return confirmed

    @staticmethod
    def _confirmed_snapshot(brief: Brief) -> PreflightSnapshot:
        if brief.preflight_snapshot is None or brief.estimated_credits is None:
            raise BriefOperationError(
                "brief_integrity_failed", "Brief 确认快照不完整", 409
            )
        return PreflightSnapshot.model_validate(brief.preflight_snapshot)

    @staticmethod
    def _brief_snapshot(brief: Brief) -> BriefSnapshot:
        return BriefSnapshot(
            brief_id=brief.id,
            brief_group_id=brief.brief_group_id,
            revision=brief.revision,
            status=brief.status,
            content=BriefWorkflowService._validated_content(brief),
            content_checksum=brief.content_checksum,
            source_snapshot=brief.source_snapshot,
            estimated_credits=brief.estimated_credits,
            confirmed_at=brief.confirmed_at,
        )


def _content_checksum(content: dict) -> str:
    canonical = json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(canonical.encode("utf-8")).hexdigest()
