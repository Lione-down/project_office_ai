import socket

import pytest

from app.services.media.videos.downloader import download_video_result
from app.services.media.videos.validation import VideoAssetValidationError


async def test_video_downloader_rejects_unapproved_or_credentialed_urls() -> None:
    for url in (
        "https://evil.example/video.mp4",
        "https://user:secret@platform-outputs.agnes-ai.space/video.mp4",
        "http://platform-outputs.agnes-ai.space/video.mp4",
    ):
        with pytest.raises(VideoAssetValidationError) as error:
            await download_video_result(
                url,
                max_bytes=1024,
                timeout_seconds=1,
                allowed_hosts=("platform-outputs.agnes-ai.space",),
            )
        assert error.value.error_code == "video_result_url_invalid"


async def test_video_downloader_rejects_private_dns_resolution(monkeypatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )

    with pytest.raises(VideoAssetValidationError) as error:
        await download_video_result(
            "https://platform-outputs.agnes-ai.space/video.mp4",
            max_bytes=1024,
            timeout_seconds=1,
            allowed_hosts=("platform-outputs.agnes-ai.space",),
        )

    assert error.value.error_code == "video_result_url_invalid"
