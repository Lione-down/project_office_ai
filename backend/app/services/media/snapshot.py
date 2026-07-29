from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_jobs import MediaJob
from app.services.media.images.service import ImageJobService
from app.services.media.videos.service import VideoJobService


async def build_media_job_snapshot(
    session: AsyncSession,
    job: MediaJob,
) -> dict:
    if job.kind == "image":
        snapshot = await ImageJobService._snapshot(session, job)
    elif job.kind == "video":
        snapshot = await VideoJobService._snapshot(session, job)
    else:
        raise ValueError("media job kind is unsupported")
    return snapshot.model_dump(mode="json")
