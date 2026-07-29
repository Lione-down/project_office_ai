import shutil
import subprocess

import pytest

from app.services.media.videos.validation import (
    VideoAssetValidationError,
    extract_video_poster,
    validate_video_bytes,
)


def synthetic_mp4() -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg is not None
    process = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x123456:s=320x180:d=1:r=24",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+frag_keyframe+empty_moov",
            "-f",
            "mp4",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    return process.stdout


def test_video_validation_uses_full_decode_and_authoritative_stream_metadata() -> None:
    payload = synthetic_mp4()
    validated = validate_video_bytes(
        payload,
        max_bytes=10 * 1024 * 1024,
        max_duration_seconds=20,
    )
    poster = extract_video_poster(validated.data)

    assert validated.mime_type == "video/mp4"
    assert validated.container == "mp4"
    assert validated.codec == "h264"
    assert validated.width == 320
    assert validated.height == 180
    assert 0.9 <= validated.duration_seconds <= 1.1
    assert validated.byte_size == len(payload)
    assert validated.sha256
    assert poster.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize(
    ("payload", "max_bytes", "max_duration"),
    [
        (b"", 1024, 20),
        (b"<html>not a video</html>", 1024, 20),
        (b"x" * 2048, 1024, 20),
    ],
)
def test_video_validation_fails_closed_for_invalid_or_oversized_content(
    payload: bytes,
    max_bytes: int,
    max_duration: int,
) -> None:
    with pytest.raises(VideoAssetValidationError):
        validate_video_bytes(
            payload,
            max_bytes=max_bytes,
            max_duration_seconds=max_duration,
        )
