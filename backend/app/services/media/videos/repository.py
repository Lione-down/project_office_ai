from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_assets import FileAsset
from app.models.media_jobs import MediaJob
from app.services.media.videos.contracts import (
    PosterAssetSummary,
    VideoAssetSummary,
    VideoJobSnapshot,
)


async def find_video_job_by_key(
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


async def find_prior_video_job(
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
            MediaJob.kind == "video",
        )
    )


async def build_video_job_snapshot(
    session: AsyncSession,
    job: MediaJob,
    *,
    replayed: bool = False,
    next_poll_after_seconds: int | None = None,
) -> VideoJobSnapshot:
    assets = list(
        await session.scalars(
            select(FileAsset).where(
                FileAsset.generated_media_job_id == job.id,
                FileAsset.asset_version == job.output_asset_version,
            )
        )
    )
    video = next((item for item in assets if item.media_role == "video"), None)
    poster = next((item for item in assets if item.media_role == "poster"), None)
    request = dict(job.capability_snapshot).get("video_request") or {}
    metadata = dict(video.media_metadata or {}) if video is not None else {}
    video_output = (
        VideoAssetSummary(
            asset_id=video.id,
            version=video.asset_version,
            mime_type=video.mime_type,
            byte_size=video.byte_size,
            sha256=video.sha256,
            width=video.media_width or 0,
            height=video.media_height or 0,
            duration_seconds=float(metadata.get("duration_seconds", 0)),
            container=metadata.get("container"),
            codec=metadata.get("codec"),
            download_path=f"/assets/{video.id}/download",
            preview_path=f"/assets/{video.id}/preview",
        )
        if video is not None
        else None
    )
    poster_output = (
        PosterAssetSummary(
            asset_id=poster.id,
            version=poster.asset_version,
            mime_type=poster.mime_type,
            byte_size=poster.byte_size,
            sha256=poster.sha256,
            width=poster.media_width or 0,
            height=poster.media_height or 0,
            preview_path=f"/assets/{poster.id}/preview",
        )
        if poster is not None
        else None
    )
    return VideoJobSnapshot(
        media_job_id=job.id,
        workflow_task_id=job.workflow_task_id,
        draft_revision_id=job.draft_revision_id,
        slide_id=job.slide_id,
        action=job.action,
        mode="text-to-video",
        status=job.status,
        progress=job.progress,
        provider_job_id=job.provider_job_id,
        model_snapshot=dict(job.model_snapshot),
        capability_snapshot=dict(job.capability_snapshot),
        pricing_snapshot=dict(job.pricing_snapshot),
        prompt_hash=job.prompt_hash,
        requested_width=int(request["width"]),
        requested_height=int(request["height"]),
        requested_num_frames=int(request["num_frames"]),
        requested_frame_rate=int(request["frame_rate"]),
        actual_width=job.actual_width,
        actual_height=job.actual_height,
        actual_duration_seconds=(
            float(metadata["duration_seconds"])
            if "duration_seconds" in metadata
            else None
        ),
        output_video=video_output,
        poster=poster_output,
        error_code=job.error_code,
        error_message=job.error_message,
        next_poll_after_seconds=next_poll_after_seconds,
        created_at=job.created_at,
        updated_at=job.updated_at,
        replayed=replayed,
    )
