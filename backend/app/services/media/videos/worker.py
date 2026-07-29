from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
import json
from time import perf_counter
from uuid import UUID

import httpx
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.credit_ledger import CreditLedger
from app.models.file_assets import FileAsset
from app.models.media_jobs import MediaJob
from app.models.provider_calls import ProviderCall
from app.models.provider_credentials import ProviderCredential
from app.models.users import User
from app.models.workflow_tasks import WorkflowTask
from app.models.base import new_uuid7, utc_now
from app.providers.agnes import ProviderVideo, VideoGenerationRequest
from app.services.media.images.repository import release_image_reserve
from app.services.media.videos.contracts import VideoJobSnapshot
from app.services.media.videos.downloader import download_video_result
from app.services.media.videos.service import VideoJobService
from app.services.media.videos.validation import (
    VideoAssetValidationError,
    extract_video_poster,
    validate_video_bytes,
)
from app.services.outbox_events import build_video_outbox_event
from app.services.provider_contracts import build_provider_adapter
from app.services.provider_security import CredentialCipher
from app.storage.local import LocalStorageAdapter, StorageOperationError


@dataclass(frozen=True)
class ClaimedVideoJob:
    job_id: UUID
    provider: AiProvider
    credential: ProviderCredential
    model: AiModel
    prompt: str
    negative_prompt: str | None
    request: dict
    provider_job_id: str | None
    operation: str


class VideoJobWorkerService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cipher: CredentialCipher,
        storage: LocalStorageAdapter,
        *,
        adapter_factory=build_provider_adapter,
        downloader=download_video_result,
        max_video_bytes: int,
        max_duration_seconds: int,
        poll_interval_seconds: int,
        job_timeout_seconds: int,
        output_host_allowlist: tuple[str, ...],
    ) -> None:
        self._session_factory = session_factory
        self._cipher = cipher
        self._storage = storage
        self._adapter_factory = adapter_factory
        self._downloader = downloader
        self._max_video_bytes = max_video_bytes
        self._max_duration_seconds = max_duration_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._job_timeout_seconds = job_timeout_seconds
        self._output_host_allowlist = output_host_allowlist

    async def process(self, job_id: UUID) -> VideoJobSnapshot:
        claimed = await self._claim(job_id)
        if isinstance(claimed, VideoJobSnapshot):
            return claimed
        adapter = self._adapter_factory(claimed.provider)
        api_key = self._cipher.decrypt(claimed.credential.encrypted_key)
        started = perf_counter()
        if claimed.operation == "submit":
            try:
                result = await adapter.create_video(
                    api_key=api_key,
                    request=VideoGenerationRequest(
                        model=claimed.model.model_code,
                        prompt=claimed.prompt,
                        width=int(claimed.request["width"]),
                        height=int(claimed.request["height"]),
                        num_frames=int(claimed.request["num_frames"]),
                        frame_rate=int(claimed.request["frame_rate"]),
                        negative_prompt=claimed.negative_prompt,
                        timeout_seconds=min(
                            claimed.provider.default_timeout_seconds,
                            120,
                        ),
                        trace_id=f"media-job:{claimed.job_id}:submit",
                    ),
                )
            except Exception as exception:
                classified = adapter.classify_error(exception)
                return await self._fail(
                    claimed,
                    category=classified.category,
                    uncertain=classified.uncertain or classified.retryable,
                    latency_ms=self._latency(started),
                    provider_request_id=None,
                )
            return await self._checkpoint_result(
                claimed,
                result,
                latency_ms=self._latency(started),
            )
        try:
            result = await adapter.get_video(
                api_key=api_key,
                model=claimed.model.model_code,
                video_id=claimed.provider_job_id,
                timeout_seconds=min(
                    claimed.provider.default_timeout_seconds,
                    120,
                ),
                trace_id=f"media-job:{claimed.job_id}:poll",
            )
        except Exception as exception:
            classified = adapter.classify_error(exception)
            if classified.retryable:
                return await self._retry_poll(
                    claimed,
                    category=classified.category,
                    latency_ms=self._latency(started),
                )
            return await self._fail(
                claimed,
                category=classified.category,
                uncertain=True,
                latency_ms=self._latency(started),
                provider_request_id=None,
            )
        return await self._checkpoint_result(
            claimed,
            result,
            latency_ms=self._latency(started),
        )

    async def _claim(
        self,
        job_id: UUID,
    ) -> ClaimedVideoJob | VideoJobSnapshot:
        async with self._session_factory() as session, session.begin():
            job = await session.get(MediaJob, job_id, with_for_update=True)
            if job is None or job.kind != "video":
                raise LookupError("video media job not found")
            if job.status not in {"queued", "submitted", "running"}:
                return await VideoJobService._snapshot(
                    session,
                    job,
                    replayed=True,
                )
            provider = await session.get(AiProvider, job.provider_id)
            credential = await session.get(ProviderCredential, job.credential_id)
            model = await session.get(AiModel, job.model_id)
            if provider is None or credential is None or model is None:
                return await self._fail_locked(
                    session,
                    job,
                    "media_capability_unavailable",
                    "视频模型能力不可用",
                )
            if (
                job.status in {"submitted", "running"}
                and job.submitted_at is not None
                and utc_now() - job.submitted_at
                >= timedelta(seconds=self._job_timeout_seconds)
            ):
                return await self._uncertain_locked(
                    session,
                    job,
                    "视频任务已超时，Provider 结果未知",
                )
            operation = "submit" if job.status == "queued" else "poll"
            if operation == "poll" and not job.provider_job_id:
                return await self._uncertain_locked(
                    session,
                    job,
                    "Provider ID 未完成 checkpoint，未重复提交",
                )
            if operation == "submit":
                job.status = "submitted"
                job.submitted_at = utc_now()
                workflow = await session.get(WorkflowTask, job.workflow_task_id)
                if workflow is not None:
                    workflow.stage = "video_submitted"
                    workflow.status = "running"
                    workflow.progress = 0
                    workflow.note = "视频请求已提交"
                    workflow.started_at = workflow.started_at or utc_now()
            try:
                prompt = json.loads(job.prompt_content)
                request = dict(job.capability_snapshot)["video_request"]
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                return await self._fail_locked(
                    session,
                    job,
                    "media_request_invalid",
                    "视频请求快照无效",
                )
            return ClaimedVideoJob(
                job_id=job.id,
                provider=provider,
                credential=credential,
                model=model,
                prompt=str(prompt["prompt"]),
                negative_prompt=prompt.get("negative_prompt"),
                request=dict(request),
                provider_job_id=job.provider_job_id,
                operation=operation,
            )

    async def _checkpoint_result(
        self,
        claimed: ClaimedVideoJob,
        result: ProviderVideo,
        *,
        latency_ms: int,
    ) -> VideoJobSnapshot:
        if result.status == "failed":
            return await self._fail(
                claimed,
                category="provider_failed",
                uncertain=False,
                latency_ms=latency_ms,
                provider_request_id=result.provider_request_id,
            )
        if result.status == "completed":
            return await self._complete(
                claimed,
                result,
                latency_ms=latency_ms,
            )
        return await self._schedule_poll(
            claimed,
            result,
            latency_ms=latency_ms,
        )

    async def _schedule_poll(
        self,
        claimed: ClaimedVideoJob,
        result: ProviderVideo,
        *,
        latency_ms: int,
    ) -> VideoJobSnapshot:
        delay = max(
            self._poll_interval_seconds,
            result.retry_after_seconds or 0,
        )
        async with self._session_factory() as session, session.begin():
            job = await session.get(MediaJob, claimed.job_id, with_for_update=True)
            if job is None:
                raise LookupError("video media job not found")
            if job.status not in {"submitted", "running"}:
                return await VideoJobService._snapshot(
                    session,
                    job,
                    replayed=True,
                )
            if job.provider_job_id not in {None, result.video_id}:
                return await self._uncertain_locked(
                    session,
                    job,
                    "Provider ID 发生冲突",
                )
            job.provider_job_id = result.video_id
            job.status = "running" if result.status == "in_progress" else "submitted"
            job.progress = result.progress
            job.actual_width = result.width
            job.actual_height = result.height
            workflow = await session.get(WorkflowTask, job.workflow_task_id)
            if workflow is not None:
                workflow.stage = "video_generating"
                workflow.status = "running"
                workflow.progress = result.progress
                workflow.note = "Provider 正在生成视频"
                workflow.dispatch_sequence += 1
                workflow.last_enqueued_at = utc_now()
                session.add(
                    build_video_outbox_event(
                        job,
                        event_type="video.poll",
                        dispatch_sequence=workflow.dispatch_sequence,
                        delay_seconds=delay,
                    )
                )
            await self._record_call(
                session,
                job,
                claimed,
                result.provider_request_id,
                latency_ms,
                job.status,
                None,
            )
            await session.flush()
            return await VideoJobService._snapshot(
                session,
                job,
                next_poll_after_seconds=delay,
            )

    async def _complete(
        self,
        claimed: ClaimedVideoJob,
        result: ProviderVideo,
        *,
        latency_ms: int,
    ) -> VideoJobSnapshot:
        if result.result_url is None:
            return await self._fail(
                claimed,
                category="provider_response_invalid",
                uncertain=True,
                latency_ms=latency_ms,
                provider_request_id=result.provider_request_id,
            )
        try:
            payload = await self._downloader(
                result.result_url,
                max_bytes=self._max_video_bytes,
                timeout_seconds=60,
                allowed_hosts=self._output_host_allowlist,
            )
            video = validate_video_bytes(
                payload,
                max_bytes=self._max_video_bytes,
                max_duration_seconds=self._max_duration_seconds,
            )
            poster_bytes = extract_video_poster(video.data)
            with Image.open(BytesIO(poster_bytes)) as poster_image:
                poster_width, poster_height = poster_image.size
        except (OSError, VideoAssetValidationError, httpx.HTTPError):
            return await self._fail(
                claimed,
                category="video_asset_invalid",
                uncertain=True,
                latency_ms=latency_ms,
                provider_request_id=result.provider_request_id,
            )
        video_asset_id = new_uuid7()
        poster_asset_id = new_uuid7()
        owner = await self._job_owner(claimed.job_id)
        try:
            video_stored = self._storage.write_media_video(
                user_id=owner,
                asset_id=video_asset_id,
                data=video.data,
            )
            poster_stored = self._storage.write_media_poster(
                user_id=owner,
                asset_id=poster_asset_id,
                data=poster_bytes,
            )
        except (OSError, StorageOperationError):
            self._safe_delete(owner, video_asset_id, locals().get("video_stored"))
            return await self._fail(
                claimed,
                category="media_storage_failed",
                uncertain=False,
                latency_ms=latency_ms,
                provider_request_id=result.provider_request_id,
            )
        try:
            return await self._persist_assets(
                claimed,
                result,
                video,
                poster_bytes,
                poster_width,
                poster_height,
                video_asset_id,
                poster_asset_id,
                video_stored.storage_key,
                poster_stored.storage_key,
                latency_ms,
            )
        except Exception:
            owner = await self._job_owner(claimed.job_id)
            self._storage.delete_asset(owner, video_asset_id, video_stored.storage_key)
            self._storage.delete_asset(
                owner, poster_asset_id, poster_stored.storage_key
            )
            raise

    async def _persist_assets(
        self,
        claimed,
        result,
        video,
        poster_bytes,
        poster_width,
        poster_height,
        video_asset_id,
        poster_asset_id,
        video_storage_key,
        poster_storage_key,
        latency_ms,
    ) -> VideoJobSnapshot:
        async with self._session_factory() as session, session.begin():
            job = await session.get(MediaJob, claimed.job_id, with_for_update=True)
            if job is None:
                raise LookupError("video media job not found")
            if job.status not in {"submitted", "running"}:
                return await VideoJobService._snapshot(session, job, replayed=True)
            job.provider_job_id = result.video_id
            job.status = "succeeded"
            job.progress = 100
            job.actual_width = video.width
            job.actual_height = video.height
            job.output_sha256 = video.sha256
            job.output_asset_version = 1
            job.error_code = None
            job.error_message = None
            job.completed_at = utc_now()
            session.add_all(
                [
                    FileAsset(
                        id=video_asset_id,
                        user_id=job.user_id,
                        project_id=job.project_id,
                        original_filename=f"slide-{job.slide_id}.mp4",
                        file_category="video",
                        mime_type=video.mime_type,
                        byte_size=video.byte_size,
                        sha256=video.sha256,
                        storage_provider=self._storage.provider,
                        storage_key=video_storage_key,
                        processing_status="ready",
                        generated_media_job_id=job.id,
                        media_role="video",
                        asset_version=1,
                        media_width=video.width,
                        media_height=video.height,
                        media_metadata={
                            "schema_version": "generated-video-asset.v1",
                            "container": video.container,
                            "codec": video.codec,
                            "duration_seconds": video.duration_seconds,
                            "frame_rate": video.frame_rate,
                            "embedding_enabled": False,
                            "fallback_mode": "poster_and_attachment",
                        },
                    ),
                    FileAsset(
                        id=poster_asset_id,
                        user_id=job.user_id,
                        project_id=job.project_id,
                        original_filename=f"slide-{job.slide_id}-poster.png",
                        file_category="image",
                        mime_type="image/png",
                        byte_size=len(poster_bytes),
                        sha256=sha256(poster_bytes).hexdigest(),
                        storage_provider=self._storage.provider,
                        storage_key=poster_storage_key,
                        processing_status="ready",
                        generated_media_job_id=job.id,
                        media_role="poster",
                        asset_version=1,
                        media_width=poster_width,
                        media_height=poster_height,
                        media_metadata={
                            "schema_version": "generated-video-poster.v1",
                            "source_video_sha256": video.sha256,
                        },
                    ),
                ]
            )
            await self._record_call(
                session,
                job,
                claimed,
                result.provider_request_id,
                latency_ms,
                "succeeded",
                None,
            )
            user = await session.get(User, job.user_id)
            if user is not None:
                session.add(
                    CreditLedger(
                        user_id=user.id,
                        task_id=None,
                        media_job_id=job.id,
                        entry_type="media_finalize",
                        amount=0,
                        balance_after=user.credit_balance,
                        related_entry_id=None,
                        idempotency_key=f"media-finalize:{job.id}",
                        description="视频生成积分结算",
                    )
                )
            workflow = await session.get(WorkflowTask, job.workflow_task_id)
            if workflow is not None:
                workflow.stage = "video_succeeded"
                workflow.status = "succeeded"
                workflow.progress = 100
                workflow.note = "视频和海报已生成并通过安全检查"
                workflow.completed_at = utc_now()
            await session.flush()
            return await VideoJobService._snapshot(session, job)

    async def _fail(
        self,
        claimed,
        *,
        category,
        uncertain,
        latency_ms,
        provider_request_id,
    ) -> VideoJobSnapshot:
        async with self._session_factory() as session, session.begin():
            job = await session.get(MediaJob, claimed.job_id, with_for_update=True)
            if job is None:
                raise LookupError("video media job not found")
            if job.status not in {"submitted", "running"}:
                return await VideoJobService._snapshot(session, job, replayed=True)
            job.status = "provider_uncertain" if uncertain else "failed"
            job.progress = 100
            job.error_code = "provider_uncertain" if uncertain else category
            job.error_message = (
                "Provider 结果未知，未自动重试"
                if uncertain
                else "视频生成或安全检查失败"
            )
            job.completed_at = utc_now()
            await self._record_call(
                session,
                job,
                claimed,
                provider_request_id,
                latency_ms,
                job.status,
                category,
            )
            if not uncertain:
                await release_image_reserve(session, job, "视频生成失败，释放积分")
            workflow = await session.get(WorkflowTask, job.workflow_task_id)
            if workflow is not None:
                workflow.stage = "video_uncertain" if uncertain else "video_failed"
                workflow.status = job.status
                workflow.progress = 100
                workflow.note = job.error_message
                workflow.failure_code = job.error_code
                workflow.failure_reason = job.error_message
                workflow.completed_at = utc_now()
            await session.flush()
            return await VideoJobService._snapshot(session, job)

    async def _retry_poll(
        self,
        claimed: ClaimedVideoJob,
        *,
        category: str,
        latency_ms: int,
    ) -> VideoJobSnapshot:
        async with self._session_factory() as session, session.begin():
            job = await session.get(MediaJob, claimed.job_id, with_for_update=True)
            if job is None:
                raise LookupError("video media job not found")
            if job.status not in {"submitted", "running"}:
                return await VideoJobService._snapshot(session, job, replayed=True)
            prior_failures = int(
                await session.scalar(
                    select(func.count(ProviderCall.id)).where(
                        ProviderCall.media_job_id == job.id,
                        ProviderCall.error_category.is_not(None),
                    )
                )
                or 0
            )
            if prior_failures >= 2:
                await self._record_call(
                    session,
                    job,
                    claimed,
                    None,
                    latency_ms,
                    "provider_uncertain",
                    category,
                )
                return await self._uncertain_locked(
                    session,
                    job,
                    "Provider 轮询连续失败，结果未知且未自动重提",
                )
            workflow = await session.get(WorkflowTask, job.workflow_task_id)
            if workflow is not None:
                workflow.dispatch_sequence += 1
                workflow.last_enqueued_at = utc_now()
                workflow.note = "Provider 轮询暂不可用，等待受限重试"
                session.add(
                    build_video_outbox_event(
                        job,
                        event_type="video.poll",
                        dispatch_sequence=workflow.dispatch_sequence,
                        delay_seconds=self._poll_interval_seconds,
                    )
                )
            await self._record_call(
                session,
                job,
                claimed,
                None,
                latency_ms,
                "retrying",
                category,
            )
            await session.flush()
            return await VideoJobService._snapshot(
                session,
                job,
                next_poll_after_seconds=self._poll_interval_seconds,
            )

    @staticmethod
    async def _record_call(
        session,
        job,
        claimed,
        provider_request_id,
        latency_ms,
        status,
        error_category,
    ) -> None:
        attempt = (
            int(
                await session.scalar(
                    select(func.max(ProviderCall.attempt)).where(
                        ProviderCall.media_job_id == job.id
                    )
                )
                or 0
            )
            + 1
        )
        session.add(
            ProviderCall(
                media_job_id=job.id,
                attempt=attempt,
                provider_id=claimed.provider.id,
                model_id=claimed.model.id,
                credential_id=claimed.credential.id,
                provider_request_id=provider_request_id,
                status=status,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=latency_ms,
                cost_amount=None,
                error_category=error_category,
                is_redacted=True,
            )
        )

    async def _fail_locked(self, session, job, code, message):
        job.status = "failed"
        job.progress = 100
        job.error_code = code
        job.error_message = message
        job.completed_at = utc_now()
        await release_image_reserve(session, job, f"{message}，释放积分")
        await self._close_workflow(session, job, "failed", message)
        return await VideoJobService._snapshot(session, job)

    async def _uncertain_locked(self, session, job, message):
        job.status = "provider_uncertain"
        job.progress = 100
        job.error_code = "provider_uncertain"
        job.error_message = message
        job.completed_at = utc_now()
        await self._close_workflow(session, job, "provider_uncertain", message)
        return await VideoJobService._snapshot(session, job)

    @staticmethod
    async def _close_workflow(session, job, status, message):
        workflow = await session.get(WorkflowTask, job.workflow_task_id)
        if workflow is not None:
            workflow.stage = (
                "video_uncertain" if status == "provider_uncertain" else "video_failed"
            )
            workflow.status = status
            workflow.progress = 100
            workflow.note = message
            workflow.failure_code = job.error_code
            workflow.failure_reason = message
            workflow.completed_at = utc_now()

    async def _job_owner(self, job_id: UUID) -> UUID:
        async with self._session_factory() as session:
            owner = await session.scalar(
                select(MediaJob.user_id).where(MediaJob.id == job_id)
            )
        if owner is None:
            raise LookupError("video media job not found")
        return owner

    def _safe_delete(self, owner: UUID, asset_id: UUID, stored) -> None:
        if stored is None:
            return
        try:
            self._storage.delete_asset(owner, asset_id, stored.storage_key)
        except (OSError, StorageOperationError):
            pass

    @staticmethod
    def _latency(started: float) -> int:
        return max(0, int((perf_counter() - started) * 1000))
