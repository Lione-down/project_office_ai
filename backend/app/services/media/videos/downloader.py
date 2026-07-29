import asyncio
from ipaddress import ip_address
import socket
from urllib.parse import urlparse

import httpx

from app.services.media.videos.validation import VideoAssetValidationError


async def download_video_result(
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: int,
    allowed_hosts: tuple[str, ...],
) -> bytes:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or hostname not in {item.lower() for item in allowed_hosts}
    ):
        raise VideoAssetValidationError(
            "video_result_url_invalid",
            "视频结果地址不受信任",
        )
    addresses = await asyncio.to_thread(
        socket.getaddrinfo,
        hostname,
        parsed.port or 443,
        type=socket.SOCK_STREAM,
    )
    if not addresses or any(not ip_address(item[4][0]).is_global for item in addresses):
        raise VideoAssetValidationError(
            "video_result_url_invalid",
            "视频结果地址不可达",
        )
    payload = bytearray()
    async with httpx.AsyncClient(follow_redirects=False) as client:
        async with client.stream(
            "GET",
            url,
            timeout=timeout_seconds,
            headers={"Accept": "video/mp4"},
        ) as response:
            if response.status_code != 200:
                raise VideoAssetValidationError(
                    "video_result_unreachable",
                    "视频结果暂不可达",
                )
            content_type = (
                response.headers.get("content-type", "")
                .split(";", 1)[0]
                .strip()
                .lower()
            )
            if content_type not in {"video/mp4", "application/octet-stream"}:
                raise VideoAssetValidationError(
                    "video_mime_invalid",
                    "视频结果类型无效",
                )
            content_length = response.headers.get("content-length")
            if (
                content_length is not None
                and content_length.isdigit()
                and int(content_length) > max_bytes
            ):
                raise VideoAssetValidationError(
                    "video_too_large",
                    "视频结果超过容量限制",
                )
            async for chunk in response.aiter_bytes():
                payload.extend(chunk)
                if len(payload) > max_bytes:
                    raise VideoAssetValidationError(
                        "video_too_large",
                        "视频结果超过容量限制",
                    )
    if not payload:
        raise VideoAssetValidationError("video_empty", "视频结果为空")
    return bytes(payload)
