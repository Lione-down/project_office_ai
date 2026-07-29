from decimal import Decimal, ROUND_CEILING
from hashlib import sha256
import json
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.credit_ledger import CreditLedger
from app.models.deck_draft_revisions import DeckDraftRevision
from app.models.deck_drafts import DeckDraft
from app.models.media_jobs import MediaJob
from app.models.provider_credentials import ProviderCredential
from app.models.users import User
from app.models.workflow_tasks import WorkflowTask
from app.models.base import utc_now
from app.services.auth_sessions import AuthSessionService, CurrentUser
from app.services.decks.contracts import DeckBrief, deck_content_checksum
from app.services.media.images.contracts import validate_media_idempotency_key
from app.services.media.images.repository import release_image_reserve
from app.services.media.videos.contracts import (
    VideoJobCreateCommand,
    VideoJobSnapshot,
    video_request_fingerprint,
)
from app.services.media.videos.repository import (
    build_video_job_snapshot,
    find_prior_video_job,
    find_video_job_by_key,
)
from app.services.media.videos.validation import (
    VideoAssetValidationError,
    validate_video_prompt_policy,
)
from app.services.outbox_events import build_video_outbox_event


ACTIVE_STATUSES = {"queued", "submitted", "running"}


class VideoJobOperationError(RuntimeError):
    def __init__(self, error_code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


class VideoJobService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
        *,
        max_active_jobs_per_user: int,
        max_prompt_chars: int,
        embedding_enabled: bool,
    ) -> None:
        if embedding_enabled:
            raise ValueError("video embedding is not supported before dual Office gate")
        self._session_factory = session_factory
        self._sessions = sessions
        self._max_active_jobs = max_active_jobs_per_user
        self._max_prompt_chars = max_prompt_chars

    async def create(
        self,
        access_token: str,
        draft_id: UUID,
        command: VideoJobCreateCommand,
        idempotency_key: str,
    ) -> VideoJobSnapshot:
        self._validate_request(command, idempotency_key)
        current_user = await self._sessions.authenticate_access(access_token)
        fingerprint = video_request_fingerprint(draft_id, command)
        try:
            async with self._session_factory() as session, session.begin():
                existing = await find_video_job_by_key(
                    session,
                    current_user.user_id,
                    idempotency_key,
                    for_update=True,
                )
                if existing is not None:
                    self._assert_replay(existing, fingerprint)
                    return await self._snapshot(session, existing, replayed=True)
                draft, revision, content = await self._load_deck(
                    session,
                    current_user,
                    draft_id,
                    command,
                )
                model, provider, credential, credits = await self._load_model(
                    session,
                    command,
                )
                active_count = await session.scalar(
                    select(func.count())
                    .select_from(MediaJob)
                    .where(
                        MediaJob.user_id == current_user.user_id,
                        MediaJob.status.in_(ACTIVE_STATUSES),
                    )
                )
                if int(active_count or 0) >= self._max_active_jobs:
                    raise VideoJobOperationError(
                        "media_concurrency_exceeded",
                        "当前已有进行中的媒体任务",
                        429,
                    )
                prior = await self._load_prior(
                    session,
                    current_user,
                    revision,
                    command,
                )
                user = await session.get(
                    User,
                    current_user.user_id,
                    with_for_update=True,
                )
                if user is None or user.status != "active":
                    raise VideoJobOperationError(
                        "session_invalid",
                        "登录状态已失效",
                        401,
                    )
                if credits != command.accepted_estimated_credits:
                    raise VideoJobOperationError(
                        "media_pricing_stale",
                        "视频生成积分已变化",
                        409,
                    )
                if user.credit_balance < credits:
                    raise VideoJobOperationError(
                        "credit_insufficient",
                        "积分不足",
                        409,
                    )
                slide = next(
                    item for item in content.slides if item.slide_id == command.slide_id
                )
                prompt_payload = json.dumps(
                    {
                        "prompt": command.prompt,
                        "negative_prompt": command.negative_prompt,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                workflow = WorkflowTask(
                    user_id=current_user.user_id,
                    project_id=draft.project_id,
                    brief_group_id=None,
                    generation_task_id=None,
                    resource_kind="media_video",
                    resource_id=None,
                    idempotency_key=f"media-workflow:{idempotency_key}"[:128],
                    title=f"{slide.title[:440]} · 视频素材",
                    request_snapshot={
                        "schema_version": "media-workflow-reference.v1",
                        "draft_revision_id": str(revision.id),
                        "slide_id": str(command.slide_id),
                        "prompt_hash": sha256(prompt_payload.encode()).hexdigest(),
                    },
                    output_kinds=["video", "poster"],
                    stage="video_queued",
                    status="queued",
                    progress=0,
                    note="视频任务已提交",
                    failure_code=None,
                    failure_reason=None,
                    dispatch_sequence=1,
                )
                session.add(workflow)
                await session.flush()
                request_snapshot = {
                    "width": command.width,
                    "height": command.height,
                    "num_frames": command.num_frames,
                    "frame_rate": command.frame_rate,
                }
                job = MediaJob(
                    user_id=current_user.user_id,
                    project_id=draft.project_id,
                    draft_revision_id=revision.id,
                    slide_id=command.slide_id,
                    workflow_task_id=workflow.id,
                    supersedes_job_id=prior.id if prior is not None else None,
                    kind="video",
                    mode="text-to-video",
                    action=command.action,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                    prompt_content=prompt_payload,
                    prompt_hash=sha256(prompt_payload.encode()).hexdigest(),
                    alt_text=f"{slide.title}的视频海报",
                    crop_mode="cover",
                    provider_id=provider.id,
                    credential_id=credential.id,
                    model_id=model.id,
                    model_snapshot={
                        "model_id": str(model.id),
                        "model_code": model.model_code,
                        "provider_id": str(provider.id),
                        "credential_id": str(credential.id),
                    },
                    capability_snapshot={
                        **dict(model.capabilities),
                        "video_request": request_snapshot,
                    },
                    pricing_snapshot={
                        "credit_per_second": model.capabilities["credit_per_second"],
                        "estimated_seconds": (command.num_frames / command.frame_rate),
                        "credits": credits,
                        "credit_multiplier": str(model.credit_multiplier),
                    },
                    status="queued",
                    progress=0,
                    provider_job_id=None,
                    requested_size=f"{command.width}x{command.height}",
                    requested_ratio=f"{command.num_frames}@{command.frame_rate}",
                    actual_width=None,
                    actual_height=None,
                    output_sha256=None,
                    output_asset_version=None,
                    estimated_credits=credits,
                    reserved_credits=credits,
                    error_code=None,
                    error_message=None,
                    cancel_requested_at=None,
                    submitted_at=None,
                    completed_at=None,
                )
                session.add(job)
                await session.flush()
                workflow.resource_id = job.id
                user.credit_balance -= credits
                session.add(
                    CreditLedger(
                        user_id=user.id,
                        task_id=None,
                        media_job_id=job.id,
                        entry_type="media_reserve",
                        amount=-credits,
                        balance_after=user.credit_balance,
                        related_entry_id=None,
                        idempotency_key=f"media-reserve:{job.id}",
                        description="视频生成积分预留",
                    )
                )
                session.add(
                    build_video_outbox_event(
                        job,
                        event_type="video.generate",
                        dispatch_sequence=workflow.dispatch_sequence,
                    )
                )
                await session.flush()
                return await self._snapshot(session, job)
        except IntegrityError:
            async with self._session_factory() as session:
                existing = await find_video_job_by_key(
                    session,
                    current_user.user_id,
                    idempotency_key,
                )
                if existing is None:
                    raise
                self._assert_replay(existing, fingerprint)
                return await self._snapshot(session, existing, replayed=True)

    async def get(self, access_token: str, job_id: UUID) -> VideoJobSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            job = await session.scalar(
                select(MediaJob).where(
                    MediaJob.id == job_id,
                    MediaJob.user_id == current_user.user_id,
                    MediaJob.kind == "video",
                )
            )
            if job is None:
                raise VideoJobOperationError(
                    "media_job_not_found",
                    "媒体任务不存在",
                    404,
                )
            return await self._snapshot(session, job)

    async def cancel(self, access_token: str, job_id: UUID) -> VideoJobSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session, session.begin():
            job = await session.scalar(
                select(MediaJob)
                .where(
                    MediaJob.id == job_id,
                    MediaJob.user_id == current_user.user_id,
                    MediaJob.kind == "video",
                )
                .with_for_update()
            )
            if job is None:
                raise VideoJobOperationError(
                    "media_job_not_found",
                    "媒体任务不存在",
                    404,
                )
            if job.status == "queued":
                await self._cancel_queued(session, job)
            elif job.status in {"submitted", "running"}:
                await self._mark_uncertain(session, job)
            return await self._snapshot(session, job)

    def _validate_request(
        self,
        command: VideoJobCreateCommand,
        idempotency_key: str,
    ) -> None:
        try:
            validate_media_idempotency_key(idempotency_key)
        except ValueError as exception:
            raise VideoJobOperationError(
                "idempotency_key_invalid",
                "Idempotency-Key 无效",
                422,
            ) from exception
        if len(command.prompt) > self._max_prompt_chars:
            raise VideoJobOperationError(
                "media_request_invalid",
                "视频 Prompt 超过运行限制",
                422,
            )
        try:
            validate_video_prompt_policy(command.prompt)
        except VideoAssetValidationError as exception:
            raise VideoJobOperationError(
                exception.error_code,
                exception.message,
                422,
            ) from exception

    @staticmethod
    async def _load_deck(
        session: AsyncSession,
        current_user: CurrentUser,
        draft_id: UUID,
        command: VideoJobCreateCommand,
    ) -> tuple[DeckDraft, DeckDraftRevision, DeckBrief]:
        draft = await session.scalar(
            select(DeckDraft).where(
                DeckDraft.id == draft_id,
                DeckDraft.user_id == current_user.user_id,
                DeckDraft.deleted_at.is_(None),
            )
        )
        if draft is None:
            raise VideoJobOperationError(
                "deck_draft_not_found",
                "Deck Draft 不存在",
                404,
            )
        if draft.latest_revision != command.expected_revision:
            raise VideoJobOperationError(
                "deck_revision_stale",
                "Deck Revision 已更新，请刷新后重试",
                409,
            )
        revision = await session.scalar(
            select(DeckDraftRevision).where(
                DeckDraftRevision.draft_id == draft.id,
                DeckDraftRevision.revision == draft.latest_revision,
            )
        )
        if revision is None or revision.status == "generation_queued":
            raise VideoJobOperationError(
                "media_request_invalid",
                "当前 Deck Revision 不允许创建视频",
                409,
            )
        try:
            content = DeckBrief.model_validate(revision.content)
        except Exception as exception:
            raise VideoJobOperationError(
                "deck_integrity_failed",
                "Deck 内容完整性校验失败",
                409,
            ) from exception
        if deck_content_checksum(
            content
        ) != revision.content_checksum or command.slide_id not in {
            slide.slide_id for slide in content.slides
        }:
            raise VideoJobOperationError(
                "deck_integrity_failed",
                "Deck 内容完整性校验失败",
                409,
            )
        return draft, revision, content

    @staticmethod
    async def _load_model(
        session: AsyncSession,
        command: VideoJobCreateCommand,
    ) -> tuple[AiModel, AiProvider, ProviderCredential, int]:
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
        if (
            model is None
            or provider is None
            or credential is None
            or model.status not in {"active", "published"}
            or not model.user_visible
            or model.capabilities.get("video_generation") is not True
            or provider.vendor != "agnes"
            or provider.status != "active"
            or credential.status != "active"
        ):
            raise VideoJobOperationError(
                "media_capability_unavailable",
                "视频模型能力不可用",
                422,
            )
        raw_credits = model.capabilities.get("credit_per_second")
        if (
            not isinstance(raw_credits, int)
            or isinstance(raw_credits, bool)
            or raw_credits < 0
        ):
            raise VideoJobOperationError(
                "media_capability_unavailable",
                "视频价格合同不可用",
                422,
            )
        seconds = Decimal(command.num_frames) / Decimal(command.frame_rate)
        credits = int(
            (
                seconds * Decimal(raw_credits) * Decimal(model.credit_multiplier)
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        return model, provider, credential, credits

    @staticmethod
    async def _load_prior(
        session: AsyncSession,
        current_user: CurrentUser,
        revision: DeckDraftRevision,
        command: VideoJobCreateCommand,
    ) -> MediaJob | None:
        if command.supersedes_job_id is None:
            return None
        prior = await find_prior_video_job(
            session,
            job_id=command.supersedes_job_id,
            user_id=current_user.user_id,
            revision_id=revision.id,
            slide_id=command.slide_id,
        )
        if prior is None:
            raise VideoJobOperationError(
                "media_job_not_found",
                "媒体任务不存在",
                404,
            )
        return prior

    @staticmethod
    def _assert_replay(job: MediaJob, fingerprint: str) -> None:
        if job.kind != "video" or job.request_fingerprint != fingerprint:
            raise VideoJobOperationError(
                "idempotency_conflict",
                "Idempotency-Key 已用于不同媒体请求",
                409,
            )

    @staticmethod
    async def _cancel_queued(session: AsyncSession, job: MediaJob) -> None:
        job.status = "cancelled"
        job.progress = 100
        job.cancel_requested_at = utc_now()
        job.completed_at = utc_now()
        await release_image_reserve(session, job, "视频任务取消，释放积分")
        workflow = await session.get(WorkflowTask, job.workflow_task_id)
        if workflow is not None:
            workflow.stage = "video_cancelled"
            workflow.status = "cancelled"
            workflow.progress = 100
            workflow.note = "视频任务已取消"
            workflow.completed_at = utc_now()

    @staticmethod
    async def _mark_uncertain(session: AsyncSession, job: MediaJob) -> None:
        job.status = "provider_uncertain"
        job.progress = 100
        job.cancel_requested_at = utc_now()
        job.completed_at = utc_now()
        job.error_code = "provider_uncertain"
        job.error_message = "Provider 未提供可验证取消，结果未知且未自动重试"
        workflow = await session.get(WorkflowTask, job.workflow_task_id)
        if workflow is not None:
            workflow.stage = "video_uncertain"
            workflow.status = "provider_uncertain"
            workflow.progress = 100
            workflow.note = job.error_message
            workflow.failure_code = job.error_code
            workflow.failure_reason = job.error_message
            workflow.completed_at = utc_now()

    @staticmethod
    async def _snapshot(
        session: AsyncSession,
        job: MediaJob,
        *,
        replayed: bool = False,
        next_poll_after_seconds: int | None = None,
    ) -> VideoJobSnapshot:
        return await build_video_job_snapshot(
            session,
            job,
            replayed=replayed,
            next_poll_after_seconds=next_poll_after_seconds,
        )
