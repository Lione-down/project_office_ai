from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.credit_ledger import CreditLedger
from app.models.file_assets import FileAsset
from app.models.media_job_inputs import MediaJobInput
from app.models.media_jobs import MediaJob
from app.models.provider_calls import ProviderCall
from app.models.provider_credentials import ProviderCredential
from app.models.users import User
from app.models.workflow_tasks import WorkflowTask
from app.models.base import new_uuid7, utc_now
from app.providers.agnes import ImageGenerationRequest
from app.services.media.images.contracts import ImageJobSnapshot
from app.services.media.images.service import ImageJobService
from app.services.media.images.validation import (
    ImageAssetValidationError,
    image_data_uri,
    validate_image_bytes,
)
from app.services.provider_contracts import build_provider_adapter
from app.services.provider_security import CredentialCipher
from app.storage.local import LocalStorageAdapter, StorageOperationError


@dataclass(frozen=True)
class ClaimedImageJob:
    job_id: UUID
    provider: AiProvider
    credential: ProviderCredential
    model: AiModel
    prompt: str
    requested_size: str
    requested_ratio: str
    input_images: tuple[str, ...]


class ImageJobWorkerService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cipher: CredentialCipher,
        storage: LocalStorageAdapter,
        *,
        adapter_factory=build_provider_adapter,
        max_image_bytes: int,
        max_decoded_bytes: int,
        provider_timeout_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._cipher = cipher
        self._storage = storage
        self._adapter_factory = adapter_factory
        self._max_image_bytes = max_image_bytes
        self._max_decoded_bytes = max_decoded_bytes
        self._provider_timeout_seconds = provider_timeout_seconds

    async def process(self, job_id: UUID) -> ImageJobSnapshot:
        claimed = await self._claim(job_id)
        if isinstance(claimed, ImageJobSnapshot):
            return claimed
        adapter = self._adapter_factory(claimed.provider)
        started = perf_counter()
        provider_request_id = None
        try:
            result = await adapter.create_image(
                api_key=self._cipher.decrypt(claimed.credential.encrypted_key),
                request=ImageGenerationRequest(
                    model=claimed.model.model_code,
                    prompt=claimed.prompt,
                    size=claimed.requested_size,
                    ratio=claimed.requested_ratio,
                    input_images=claimed.input_images,
                    timeout_seconds=min(
                        claimed.provider.default_timeout_seconds,
                        self._provider_timeout_seconds,
                    ),
                    trace_id=f"media-job:{claimed.job_id}",
                ),
            )
            provider_request_id = result.provider_request_id
            validated = validate_image_bytes(
                result.image_bytes,
                max_bytes=self._max_image_bytes,
                max_decoded_bytes=self._max_decoded_bytes,
            )
        except Exception as exception:
            if isinstance(exception, ImageAssetValidationError):
                category = exception.error_code
                uncertain = False
            else:
                classified = adapter.classify_error(exception)
                category = classified.category
                uncertain = classified.uncertain
            return await self._fail(
                claimed,
                category=category,
                uncertain=uncertain,
                latency_ms=max(0, int((perf_counter() - started) * 1000)),
                provider_request_id=provider_request_id,
            )
        asset_id = new_uuid7()
        try:
            stored = self._storage.write_media_image(
                user_id=(await self._job_owner(claimed.job_id)),
                asset_id=asset_id,
                extension=validated.extension,
                data=validated.data,
            )
        except (OSError, StorageOperationError):
            return await self._fail(
                claimed,
                category="media_storage_failed",
                uncertain=False,
                latency_ms=max(0, int((perf_counter() - started) * 1000)),
                provider_request_id=provider_request_id,
            )
        try:
            return await self._complete(
                claimed,
                result.provider_request_id,
                validated,
                asset_id,
                stored.storage_key,
                max(0, int((perf_counter() - started) * 1000)),
            )
        except Exception:
            self._storage.delete_asset(
                await self._job_owner(claimed.job_id),
                asset_id,
                stored.storage_key,
            )
            raise

    async def _claim(
        self,
        job_id: UUID,
    ) -> ClaimedImageJob | ImageJobSnapshot:
        async with self._session_factory() as session, session.begin():
            job = await session.get(MediaJob, job_id, with_for_update=True)
            if job is None:
                raise LookupError("media job not found")
            if job.status != "queued":
                return await ImageJobService._snapshot(session, job, replayed=True)
            provider = await session.get(AiProvider, job.provider_id)
            credential = await session.get(ProviderCredential, job.credential_id)
            model = await session.get(AiModel, job.model_id)
            if provider is None or credential is None or model is None:
                job.status = "failed"
                job.progress = 100
                job.error_code = "media_capability_unavailable"
                job.error_message = "图片模型能力不可用"
                job.completed_at = utc_now()
                await ImageJobService._release_reserve(
                    session,
                    job,
                    "图片模型能力不可用，释放积分",
                )
                workflow = await session.get(WorkflowTask, job.workflow_task_id)
                if workflow is not None:
                    workflow.stage = "image_failed"
                    workflow.status = "failed"
                    workflow.progress = 100
                    workflow.note = job.error_message
                    workflow.failure_code = job.error_code
                    workflow.failure_reason = job.error_message
                    workflow.completed_at = utc_now()
                return await ImageJobService._snapshot(session, job)
            try:
                input_images = await self._load_inputs(session, job)
            except (ImageAssetValidationError, OSError, ValueError):
                job.status = "failed"
                job.progress = 100
                job.error_code = "media_input_invalid"
                job.error_message = "图片输入资产不可用"
                job.completed_at = utc_now()
                await ImageJobService._release_reserve(
                    session,
                    job,
                    "图片输入无效，释放积分",
                )
                workflow = await session.get(WorkflowTask, job.workflow_task_id)
                if workflow is not None:
                    workflow.stage = "image_failed"
                    workflow.status = "failed"
                    workflow.progress = 100
                    workflow.note = job.error_message
                    workflow.failure_code = job.error_code
                    workflow.failure_reason = job.error_message
                    workflow.completed_at = utc_now()
                return await ImageJobService._snapshot(session, job)
            job.status = "submitted"
            job.progress = 10
            job.submitted_at = utc_now()
            workflow = await session.get(WorkflowTask, job.workflow_task_id)
            if workflow is not None:
                workflow.stage = "image_generating"
                workflow.status = "running"
                workflow.progress = 10
                workflow.note = "正在生成图片"
                workflow.started_at = workflow.started_at or utc_now()
            return ClaimedImageJob(
                job_id=job.id,
                provider=provider,
                credential=credential,
                model=model,
                prompt=job.prompt_content,
                requested_size=job.requested_size,
                requested_ratio=job.requested_ratio,
                input_images=input_images,
            )

    async def _load_inputs(
        self,
        session: AsyncSession,
        job: MediaJob,
    ) -> tuple[str, ...]:
        inputs = list(
            await session.scalars(
                select(MediaJobInput)
                .where(MediaJobInput.media_job_id == job.id)
                .order_by(MediaJobInput.sequence)
            )
        )
        data_uris = []
        for item in inputs:
            asset = await session.get(FileAsset, item.source_asset_id)
            if (
                asset is None
                or asset.user_id != job.user_id
                or asset.project_id != job.project_id
                or asset.deleted_at is not None
                or asset.processing_status != "ready"
                or asset.file_category != "image"
                or asset.asset_version != item.source_asset_version
                or asset.sha256 != item.source_sha256
            ):
                raise ImageAssetValidationError(
                    "media_input_invalid", "图片输入资产不可用"
                )
            path = self._storage.resolve_asset_key(
                job.user_id, asset.id, asset.storage_key
            )
            validated = validate_image_bytes(
                path.read_bytes(),
                max_bytes=self._max_image_bytes,
                max_decoded_bytes=self._max_decoded_bytes,
            )
            if validated.sha256 != asset.sha256:
                raise ImageAssetValidationError(
                    "media_input_invalid", "图片输入资产完整性校验失败"
                )
            data_uris.append(image_data_uri(validated))
        return tuple(data_uris)

    async def _complete(
        self,
        claimed: ClaimedImageJob,
        provider_request_id: str | None,
        image,
        asset_id: UUID,
        storage_key: str,
        latency_ms: int,
    ) -> ImageJobSnapshot:
        async with self._session_factory() as session, session.begin():
            job = await session.get(MediaJob, claimed.job_id, with_for_update=True)
            if job is None:
                raise LookupError("media job not found")
            if job.status != "submitted":
                return await ImageJobService._snapshot(session, job, replayed=True)
            job.provider_job_id = provider_request_id
            job.status = "succeeded"
            job.progress = 100
            job.actual_width = image.width
            job.actual_height = image.height
            job.output_sha256 = image.sha256
            job.output_asset_version = 1
            job.error_code = None
            job.error_message = None
            job.completed_at = utc_now()
            asset = FileAsset(
                id=asset_id,
                user_id=job.user_id,
                project_id=job.project_id,
                original_filename=f"slide-{job.slide_id}.png",
                file_category="image",
                mime_type=image.mime_type,
                byte_size=image.byte_size,
                sha256=image.sha256,
                storage_provider=self._storage.provider,
                storage_key=storage_key,
                processing_status="ready",
                idempotency_key=None,
                parent_asset_id=None,
                generated_task_id=None,
                generated_media_job_id=job.id,
                media_role="image",
                asset_version=1,
                media_width=image.width,
                media_height=image.height,
                media_metadata={
                    "schema_version": "generated-image-asset.v1",
                    "crop_mode": job.crop_mode,
                    "alt_text": job.alt_text,
                    "prompt_policy": "prompt-policy.v1",
                    "provider_safety": "contractual",
                },
            )
            session.add(asset)
            self._record_call(
                session,
                job,
                claimed,
                provider_request_id,
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
                        description="图片生成积分结算",
                    )
                )
            workflow = await session.get(WorkflowTask, job.workflow_task_id)
            if workflow is not None:
                workflow.stage = "image_succeeded"
                workflow.status = "succeeded"
                workflow.progress = 100
                workflow.note = "图片已生成并通过安全检查"
                workflow.completed_at = utc_now()
            await session.flush()
            return await ImageJobService._snapshot(session, job)

    async def _fail(
        self,
        claimed: ClaimedImageJob,
        *,
        category: str,
        uncertain: bool,
        latency_ms: int,
        provider_request_id: str | None = None,
    ) -> ImageJobSnapshot:
        async with self._session_factory() as session, session.begin():
            job = await session.get(MediaJob, claimed.job_id, with_for_update=True)
            if job is None:
                raise LookupError("media job not found")
            if job.status != "submitted":
                return await ImageJobService._snapshot(session, job, replayed=True)
            job.status = "provider_uncertain" if uncertain else "failed"
            job.progress = 100
            job.error_code = "provider_uncertain" if uncertain else category
            job.error_message = (
                "Provider 结果未知，未自动重试"
                if uncertain
                else "图片生成或安全检查失败"
            )
            job.completed_at = utc_now()
            self._record_call(
                session,
                job,
                claimed,
                provider_request_id,
                latency_ms,
                job.status,
                category,
            )
            if not uncertain:
                await ImageJobService._release_reserve(
                    session, job, "图片生成失败，释放积分"
                )
            workflow = await session.get(WorkflowTask, job.workflow_task_id)
            if workflow is not None:
                workflow.stage = "image_failed"
                workflow.status = job.status
                workflow.progress = 100
                workflow.note = job.error_message
                workflow.failure_code = job.error_code
                workflow.failure_reason = job.error_message
                workflow.completed_at = utc_now()
            await session.flush()
            return await ImageJobService._snapshot(session, job)

    @staticmethod
    def _record_call(
        session: AsyncSession,
        job: MediaJob,
        claimed: ClaimedImageJob,
        provider_request_id: str | None,
        latency_ms: int,
        status: str,
        error_category: str | None,
    ) -> None:
        session.add(
            ProviderCall(
                media_job_id=job.id,
                attempt=1,
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

    async def _job_owner(self, job_id: UUID) -> UUID:
        async with self._session_factory() as session:
            user_id = await session.scalar(
                select(MediaJob.user_id).where(MediaJob.id == job_id)
            )
        if user_id is None:
            raise LookupError("media job not found")
        return user_id
