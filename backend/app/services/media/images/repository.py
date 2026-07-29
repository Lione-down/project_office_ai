from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_ledger import CreditLedger
from app.models.file_assets import FileAsset
from app.models.media_jobs import MediaJob
from app.models.users import User
from app.services.media.images.contracts import ImageAssetSummary, ImageJobSnapshot


async def find_image_job_by_key(
    session: AsyncSession,
    user_id: UUID,
    key: str,
    *,
    for_update: bool = False,
) -> MediaJob | None:
    statement = select(MediaJob).where(
        MediaJob.user_id == user_id,
        MediaJob.idempotency_key == key,
    )
    if for_update:
        statement = statement.with_for_update()
    return await session.scalar(statement)


async def find_prior_image_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    user_id: UUID,
    revision_id: UUID,
    slide_id: UUID,
) -> MediaJob | None:
    return await session.scalar(
        select(MediaJob).where(
            MediaJob.id == job_id,
            MediaJob.user_id == user_id,
            MediaJob.draft_revision_id == revision_id,
            MediaJob.slide_id == slide_id,
            MediaJob.kind == "image",
        )
    )


async def find_input_image_asset(
    session: AsyncSession,
    *,
    asset_id: UUID,
    user_id: UUID,
    project_id: UUID,
) -> FileAsset | None:
    return await session.scalar(
        select(FileAsset).where(
            FileAsset.id == asset_id,
            FileAsset.user_id == user_id,
            FileAsset.project_id == project_id,
            FileAsset.deleted_at.is_(None),
        )
    )


async def release_image_reserve(
    session: AsyncSession,
    job: MediaJob,
    description: str,
) -> None:
    if job.reserved_credits <= 0:
        return
    user = await session.get(User, job.user_id, with_for_update=True)
    if user is None:
        return
    user.credit_balance += job.reserved_credits
    session.add(
        CreditLedger(
            user_id=user.id,
            task_id=None,
            media_job_id=job.id,
            entry_type="media_release",
            amount=job.reserved_credits,
            balance_after=user.credit_balance,
            related_entry_id=None,
            idempotency_key=f"media-release:{job.id}",
            description=description,
        )
    )


async def build_image_job_snapshot(
    session: AsyncSession,
    job: MediaJob,
    *,
    replayed: bool = False,
) -> ImageJobSnapshot:
    asset = await session.scalar(
        select(FileAsset).where(
            FileAsset.generated_media_job_id == job.id,
            FileAsset.media_role == "image",
            FileAsset.asset_version == job.output_asset_version,
        )
    )
    output = (
        ImageAssetSummary(
            asset_id=asset.id,
            version=asset.asset_version,
            mime_type=asset.mime_type,
            byte_size=asset.byte_size,
            sha256=asset.sha256,
            width=asset.media_width or 0,
            height=asset.media_height or 0,
        )
        if asset is not None
        else None
    )
    return ImageJobSnapshot(
        media_job_id=job.id,
        workflow_task_id=job.workflow_task_id,
        draft_revision_id=job.draft_revision_id,
        slide_id=job.slide_id,
        action=job.action,
        status=job.status,
        progress=job.progress,
        model_snapshot=dict(job.model_snapshot),
        capability_snapshot=dict(job.capability_snapshot),
        pricing_snapshot=dict(job.pricing_snapshot),
        prompt_hash=job.prompt_hash,
        requested_size=job.requested_size,
        requested_ratio=job.requested_ratio,
        crop_mode=job.crop_mode,
        alt_text=job.alt_text,
        actual_width=job.actual_width,
        actual_height=job.actual_height,
        output_asset=output,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        replayed=replayed,
    )
