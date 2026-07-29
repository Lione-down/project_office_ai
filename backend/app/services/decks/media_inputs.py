from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deck_draft_revisions import DeckDraftRevision
from app.models.deck_drafts import DeckDraft
from app.models.file_assets import FileAsset
from app.models.media_jobs import MediaJob
from app.services.decks.contracts import DeckOperationError


async def build_deck_media_inputs(
    session: AsyncSession,
    draft: DeckDraft,
    row: DeckDraftRevision,
) -> tuple[dict, ...]:
    jobs = list(
        await session.scalars(
            select(MediaJob)
            .where(
                MediaJob.user_id == draft.user_id,
                MediaJob.project_id == draft.project_id,
                MediaJob.draft_revision_id == row.id,
                MediaJob.kind.in_(("image", "video")),
                MediaJob.status == "succeeded",
            )
            .order_by(MediaJob.created_at, MediaJob.id)
        )
    )
    latest_by_slide = {job.slide_id: job for job in jobs}
    inputs: list[dict] = []
    for slide_id, job in latest_by_slide.items():
        if job.kind == "image":
            inputs.append(await _image_input(session, draft, row, job))
            continue
        poster, attachment = await _video_inputs(session, draft, row, job)
        inputs.extend((poster, attachment))
    return tuple(inputs)


async def _image_input(
    session: AsyncSession,
    draft: DeckDraft,
    row: DeckDraftRevision,
    job: MediaJob,
) -> dict:
    asset = await session.scalar(
        select(FileAsset).where(
            FileAsset.generated_media_job_id == job.id,
            FileAsset.media_role == "image",
            FileAsset.asset_version == job.output_asset_version,
        )
    )
    if not _owned_ready_asset(asset, draft) or (
        asset.mime_type not in {"image/png", "image/jpeg"}
        or asset.sha256 != job.output_sha256
        or asset.media_width != job.actual_width
        or asset.media_height != job.actual_height
    ):
        raise DeckOperationError(
            "deck_image_asset_invalid",
            "Deck 图片资产完整性校验失败",
            409,
        )
    return _poster_input(
        row,
        job,
        asset,
        source_kind="image",
        media_role="image",
        crop_mode=job.crop_mode,
        alt_text=job.alt_text,
    )


async def _video_inputs(
    session: AsyncSession,
    draft: DeckDraft,
    row: DeckDraftRevision,
    job: MediaJob,
) -> tuple[dict, dict]:
    assets = list(
        await session.scalars(
            select(FileAsset).where(
                FileAsset.generated_media_job_id == job.id,
                FileAsset.asset_version == job.output_asset_version,
                FileAsset.media_role.in_(("poster", "video")),
            )
        )
    )
    by_role = {asset.media_role: asset for asset in assets}
    poster = by_role.get("poster")
    video = by_role.get("video")
    if not _owned_ready_asset(poster, draft) or not _owned_ready_asset(video, draft):
        raise DeckOperationError(
            "deck_video_asset_invalid",
            "Deck 视频资产完整性校验失败",
            409,
        )
    metadata = video.media_metadata if isinstance(video.media_metadata, dict) else {}
    poster_metadata = (
        poster.media_metadata if isinstance(poster.media_metadata, dict) else {}
    )
    if (
        video.mime_type != "video/mp4"
        or video.sha256 != job.output_sha256
        or video.media_width != job.actual_width
        or video.media_height != job.actual_height
        or metadata.get("container") != "mp4"
        or metadata.get("codec") != "h264"
        or metadata.get("embedding_enabled") is not False
        or metadata.get("fallback_mode") != "poster_and_attachment"
        or poster.mime_type != "image/png"
        or poster_metadata.get("source_video_sha256") != video.sha256
    ):
        raise DeckOperationError(
            "deck_video_asset_invalid",
            "Deck 视频资产完整性校验失败",
            409,
        )
    poster_input = _poster_input(
        row,
        job,
        poster,
        source_kind="video_poster",
        media_role="poster",
        crop_mode="contain",
        alt_text="视频预览图；MP4 作为独立附件交付",
    )
    attachment_input = {
        "input_type": "media_video_attachment",
        "reference_key": str(job.slide_id),
        "snapshot": {
            "draft_revision_id": str(row.id),
            "slide_id": str(job.slide_id),
            "media_job_id": str(job.id),
            "asset_id": str(video.id),
            "asset_version": video.asset_version,
            "media_role": "video",
            "mime_type": video.mime_type,
            "byte_size": video.byte_size,
            "sha256": video.sha256,
            "width": video.media_width,
            "height": video.media_height,
            "duration_seconds": metadata["duration_seconds"],
            "container": "mp4",
            "codec": "h264",
            "embedding_enabled": False,
            "fallback_mode": "poster_and_attachment",
        },
    }
    return poster_input, attachment_input


def _poster_input(
    row: DeckDraftRevision,
    job: MediaJob,
    asset: FileAsset,
    *,
    source_kind: str,
    media_role: str,
    crop_mode: str,
    alt_text: str,
) -> dict:
    return {
        "input_type": "media_image",
        "reference_key": str(job.slide_id),
        "snapshot": {
            "draft_revision_id": str(row.id),
            "slide_id": str(job.slide_id),
            "media_job_id": str(job.id),
            "asset_id": str(asset.id),
            "asset_version": asset.asset_version,
            "source_kind": source_kind,
            "media_role": media_role,
            "mime_type": asset.mime_type,
            "byte_size": asset.byte_size,
            "sha256": asset.sha256,
            "width": asset.media_width,
            "height": asset.media_height,
            "crop_mode": crop_mode,
            "alt_text": alt_text,
        },
    }


def _owned_ready_asset(asset: FileAsset | None, draft: DeckDraft) -> bool:
    return bool(
        asset is not None
        and asset.user_id == draft.user_id
        and asset.project_id == draft.project_id
        and asset.deleted_at is None
        and asset.processing_status == "ready"
    )
