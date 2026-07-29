from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.credit_ledger import CreditLedger
from app.models.deck_draft_revisions import DeckDraftRevision
from app.models.deck_drafts import DeckDraft
from app.models.file_assets import FileAsset
from app.models.media_job_inputs import MediaJobInput
from app.models.media_jobs import MediaJob
from app.models.provider_credentials import ProviderCredential
from app.models.users import User
from app.models.workflow_tasks import WorkflowTask
from app.models.base import utc_now
from app.services.auth_sessions import AuthSessionService, CurrentUser
from app.services.decks.contracts import DeckBrief, deck_content_checksum
from app.services.media.images.contracts import (
    ImageJobCreateCommand,
    ImageJobSnapshot,
    image_request_fingerprint,
    validate_media_idempotency_key,
)
from app.services.media.images.repository import (
    build_image_job_snapshot,
    find_image_job_by_key,
    find_input_image_asset,
    find_prior_image_job,
    release_image_reserve,
)
from app.services.media.images.validation import (
    ImageAssetValidationError,
    validate_image_prompt_policy,
)
from app.services.outbox_events import build_image_outbox_event


ACTIVE_STATUSES = {"queued", "submitted", "running"}


class ImageJobOperationError(RuntimeError):
    def __init__(self, error_code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


class ImageJobService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
        *,
        max_active_jobs_per_user: int,
        max_prompt_chars: int,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions
        self._max_active_jobs = max_active_jobs_per_user
        self._max_prompt_chars = max_prompt_chars

    async def create(
        self,
        access_token: str,
        draft_id: UUID,
        command: ImageJobCreateCommand,
        idempotency_key: str,
    ) -> ImageJobSnapshot:
        try:
            validate_media_idempotency_key(idempotency_key)
        except ValueError as exception:
            raise ImageJobOperationError(
                "idempotency_key_invalid", "Idempotency-Key 无效", 422
            ) from exception
        if len(command.prompt) > self._max_prompt_chars:
            raise ImageJobOperationError(
                "media_request_invalid", "图片 Prompt 超过运行限制", 422
            )
        try:
            validate_image_prompt_policy(command.prompt)
        except ImageAssetValidationError as exception:
            raise ImageJobOperationError(
                exception.error_code,
                exception.message,
                422,
            ) from exception
        current_user = await self._sessions.authenticate_access(access_token)
        fingerprint = image_request_fingerprint(draft_id, command)
        try:
            async with self._session_factory() as session, session.begin():
                existing = await find_image_job_by_key(
                    session,
                    current_user.user_id,
                    idempotency_key,
                    for_update=True,
                )
                if existing is not None:
                    self._assert_replay(existing, fingerprint)
                    return await self._snapshot(session, existing, replayed=True)
                draft, revision, content = await self._load_deck(
                    session, current_user, draft_id, command
                )
                model, provider, credential, credits = await self._load_model(
                    session, command
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
                    raise ImageJobOperationError(
                        "media_concurrency_exceeded",
                        "当前已有进行中的媒体任务",
                        429,
                    )
                prior = await self._load_prior(session, current_user, revision, command)
                input_asset = await self._load_input_asset(
                    session, current_user, draft, command
                )
                user = await session.get(
                    User, current_user.user_id, with_for_update=True
                )
                if user is None or user.status != "active":
                    raise ImageJobOperationError(
                        "session_invalid", "登录状态已失效", 401
                    )
                if credits != command.accepted_estimated_credits:
                    raise ImageJobOperationError(
                        "media_pricing_stale", "图片生成积分已变化", 409
                    )
                if user.credit_balance < credits:
                    raise ImageJobOperationError("credit_insufficient", "积分不足", 409)
                slide = next(
                    item for item in content.slides if item.slide_id == command.slide_id
                )
                workflow = WorkflowTask(
                    user_id=current_user.user_id,
                    project_id=draft.project_id,
                    brief_group_id=None,
                    generation_task_id=None,
                    resource_kind="media_image",
                    resource_id=None,
                    idempotency_key=f"media-workflow:{idempotency_key}"[:128],
                    title=f"{slide.title[:440]} · 图片素材",
                    request_snapshot={
                        "schema_version": "media-workflow-reference.v1",
                        "draft_revision_id": str(revision.id),
                        "slide_id": str(command.slide_id),
                        "prompt_hash": sha256(
                            command.prompt.encode("utf-8")
                        ).hexdigest(),
                    },
                    output_kinds=["image"],
                    stage="image_queued",
                    status="queued",
                    progress=0,
                    note="图片任务已提交",
                    failure_code=None,
                    failure_reason=None,
                    dispatch_sequence=1,
                )
                session.add(workflow)
                await session.flush()
                job = MediaJob(
                    user_id=current_user.user_id,
                    project_id=draft.project_id,
                    draft_revision_id=revision.id,
                    slide_id=command.slide_id,
                    workflow_task_id=workflow.id,
                    supersedes_job_id=prior.id if prior is not None else None,
                    kind="image",
                    mode=(
                        "image-to-image"
                        if command.input_asset_id is not None
                        else "text-to-image"
                    ),
                    action=command.action,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                    prompt_content=command.prompt,
                    prompt_hash=sha256(command.prompt.encode("utf-8")).hexdigest(),
                    alt_text=command.alt_text,
                    crop_mode=command.crop_mode,
                    provider_id=provider.id,
                    credential_id=credential.id,
                    model_id=model.id,
                    model_snapshot={
                        "model_id": str(model.id),
                        "model_code": model.model_code,
                        "provider_id": str(provider.id),
                        "credential_id": str(credential.id),
                    },
                    capability_snapshot=dict(model.capabilities),
                    pricing_snapshot={
                        "credit_per_image": credits,
                        "credit_multiplier": str(model.credit_multiplier),
                    },
                    status="queued",
                    progress=0,
                    provider_job_id=None,
                    requested_size=command.requested_size,
                    requested_ratio=command.requested_ratio,
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
                if input_asset is not None:
                    session.add(
                        MediaJobInput(
                            media_job_id=job.id,
                            input_kind="image",
                            source_asset_id=input_asset.id,
                            source_asset_version=input_asset.asset_version,
                            source_sha256=input_asset.sha256,
                            slide_id=command.slide_id,
                            sequence=1,
                            purpose="img2img",
                        )
                    )
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
                        description="图片生成积分预留",
                    )
                )
                session.add(build_image_outbox_event(job))
                await session.flush()
                return await self._snapshot(session, job)
        except IntegrityError:
            async with self._session_factory() as session:
                existing = await find_image_job_by_key(
                    session, current_user.user_id, idempotency_key
                )
                if existing is None:
                    raise
                self._assert_replay(existing, fingerprint)
                return await self._snapshot(session, existing, replayed=True)

    async def get(
        self,
        access_token: str,
        job_id: UUID,
    ) -> ImageJobSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            job = await session.scalar(
                select(MediaJob).where(
                    MediaJob.id == job_id,
                    MediaJob.user_id == current_user.user_id,
                    MediaJob.kind == "image",
                )
            )
            if job is None:
                raise ImageJobOperationError(
                    "media_job_not_found", "媒体任务不存在", 404
                )
            return await self._snapshot(session, job)

    async def cancel(
        self,
        access_token: str,
        job_id: UUID,
    ) -> ImageJobSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session, session.begin():
            job = await session.scalar(
                select(MediaJob)
                .where(
                    MediaJob.id == job_id,
                    MediaJob.user_id == current_user.user_id,
                    MediaJob.kind == "image",
                )
                .with_for_update()
            )
            if job is None:
                raise ImageJobOperationError(
                    "media_job_not_found", "媒体任务不存在", 404
                )
            if job.status == "queued":
                job.status = "cancelled"
                job.progress = 100
                job.cancel_requested_at = utc_now()
                job.completed_at = utc_now()
                await self._release_reserve(session, job, "media_cancelled")
                workflow = await session.get(WorkflowTask, job.workflow_task_id)
                if workflow is not None:
                    workflow.stage = "image_cancelled"
                    workflow.status = "cancelled"
                    workflow.progress = 100
                    workflow.note = "图片任务已取消"
                    workflow.completed_at = utc_now()
            elif job.status in {"submitted", "running"}:
                job.status = "provider_uncertain"
                job.progress = 100
                job.cancel_requested_at = utc_now()
                job.completed_at = utc_now()
                job.error_code = "provider_uncertain"
                job.error_message = "Provider 结果未知，未自动重试"
                workflow = await session.get(WorkflowTask, job.workflow_task_id)
                if workflow is not None:
                    workflow.stage = "image_failed"
                    workflow.status = "provider_uncertain"
                    workflow.progress = 100
                    workflow.note = job.error_message
                    workflow.failure_code = job.error_code
                    workflow.failure_reason = job.error_message
                    workflow.completed_at = utc_now()
            return await self._snapshot(session, job)

    async def _load_deck(
        self,
        session: AsyncSession,
        current_user: CurrentUser,
        draft_id: UUID,
        command: ImageJobCreateCommand,
    ) -> tuple[DeckDraft, DeckDraftRevision, DeckBrief]:
        draft = await session.scalar(
            select(DeckDraft).where(
                DeckDraft.id == draft_id,
                DeckDraft.user_id == current_user.user_id,
                DeckDraft.deleted_at.is_(None),
            )
        )
        if draft is None:
            raise ImageJobOperationError(
                "deck_draft_not_found", "Deck Draft 不存在", 404
            )
        if draft.latest_revision != command.expected_revision:
            raise ImageJobOperationError(
                "deck_revision_stale", "Deck Revision 已更新，请刷新后重试", 409
            )
        revision = await session.scalar(
            select(DeckDraftRevision).where(
                DeckDraftRevision.draft_id == draft.id,
                DeckDraftRevision.revision == draft.latest_revision,
            )
        )
        if revision is None or revision.status == "generation_queued":
            raise ImageJobOperationError(
                "media_request_invalid", "当前 Deck Revision 不允许创建图片", 409
            )
        try:
            content = DeckBrief.model_validate(revision.content)
        except Exception as exception:
            raise ImageJobOperationError(
                "deck_integrity_failed", "Deck 内容完整性校验失败", 409
            ) from exception
        if deck_content_checksum(
            content
        ) != revision.content_checksum or command.slide_id not in {
            slide.slide_id for slide in content.slides
        }:
            raise ImageJobOperationError(
                "deck_integrity_failed", "Deck 内容完整性校验失败", 409
            )
        return draft, revision, content

    @staticmethod
    async def _load_model(
        session: AsyncSession,
        command: ImageJobCreateCommand,
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
            or model.capabilities.get("image_generation") is not True
            or provider.vendor != "agnes"
            or provider.status != "active"
            or credential.status != "active"
        ):
            raise ImageJobOperationError(
                "media_capability_unavailable", "图片模型能力不可用", 422
            )
        raw_credits = model.capabilities.get("credit_per_image")
        if (
            not isinstance(raw_credits, int)
            or isinstance(raw_credits, bool)
            or raw_credits < 0
        ):
            raise ImageJobOperationError(
                "media_capability_unavailable", "图片价格合同不可用", 422
            )
        credits = int(raw_credits * model.credit_multiplier)
        return model, provider, credential, credits

    @staticmethod
    async def _load_prior(
        session: AsyncSession,
        current_user: CurrentUser,
        revision: DeckDraftRevision,
        command: ImageJobCreateCommand,
    ) -> MediaJob | None:
        if command.supersedes_job_id is None:
            return None
        prior = await find_prior_image_job(
            session,
            job_id=command.supersedes_job_id,
            user_id=current_user.user_id,
            revision_id=revision.id,
            slide_id=command.slide_id,
        )
        if prior is None:
            raise ImageJobOperationError("media_job_not_found", "媒体任务不存在", 404)
        return prior

    @staticmethod
    async def _load_input_asset(
        session: AsyncSession,
        current_user: CurrentUser,
        draft: DeckDraft,
        command: ImageJobCreateCommand,
    ) -> FileAsset | None:
        if command.input_asset_id is None:
            return None
        asset = await find_input_image_asset(
            session,
            asset_id=command.input_asset_id,
            user_id=current_user.user_id,
            project_id=draft.project_id,
        )
        if (
            asset is None
            or asset.file_category != "image"
            or asset.processing_status != "ready"
            or asset.asset_version != command.input_asset_version
            or asset.mime_type not in {"image/png", "image/jpeg"}
        ):
            raise ImageJobOperationError(
                "media_input_invalid", "图片输入资产不可用", 422
            )
        return asset

    @staticmethod
    def _assert_replay(job: MediaJob, fingerprint: str) -> None:
        if job.request_fingerprint != fingerprint:
            raise ImageJobOperationError(
                "idempotency_conflict",
                "Idempotency-Key 已用于不同图片请求",
                409,
            )

    @staticmethod
    async def _release_reserve(
        session: AsyncSession,
        job: MediaJob,
        description: str,
    ) -> None:
        await release_image_reserve(session, job, description)

    @staticmethod
    async def _snapshot(
        session: AsyncSession,
        job: MediaJob,
        *,
        replayed: bool = False,
    ) -> ImageJobSnapshot:
        return await build_image_job_snapshot(session, job, replayed=replayed)
