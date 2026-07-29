from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from PIL import Image


class VideoAssetValidationError(ValueError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


@dataclass(frozen=True)
class ValidatedVideo:
    data: bytes
    mime_type: str
    container: str
    codec: str
    width: int
    height: int
    duration_seconds: float
    frame_rate: float
    byte_size: int
    sha256: str
    extension: str


def validate_video_prompt_policy(prompt: str) -> None:
    normalized = re.sub(r"\s+", " ", prompt).strip().lower()
    if re.search(r"\b(child|minor)\b.{0,40}\bsexual\b", normalized):
        raise VideoAssetValidationError(
            "video_content_policy_rejected",
            "视频内容请求不符合安全策略",
        )


def validate_video_bytes(
    data: bytes,
    *,
    max_bytes: int,
    max_duration_seconds: int,
) -> ValidatedVideo:
    if not data:
        raise VideoAssetValidationError("video_empty", "视频结果为空")
    if len(data) > max_bytes:
        raise VideoAssetValidationError("video_too_large", "视频结果超过容量限制")
    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if ffprobe is None or ffmpeg is None:
        raise VideoAssetValidationError(
            "video_decoder_unavailable",
            "视频安全解码器不可用",
        )
    with tempfile.TemporaryDirectory(prefix="office-ai-video-") as directory:
        path = Path(directory) / "result.mp4"
        path.write_bytes(data)
        metadata = _probe_video(ffprobe, path)
        stream = _select_video_stream(metadata)
        format_names = {
            item.strip()
            for item in str(metadata.get("format", {}).get("format_name", "")).split(
                ","
            )
            if item.strip()
        }
        if not {"mov", "mp4"}.intersection(format_names):
            raise VideoAssetValidationError(
                "video_container_invalid",
                "视频容器不受支持",
            )
        if stream.get("codec_name") != "h264":
            raise VideoAssetValidationError(
                "video_codec_invalid",
                "视频编码不受支持",
            )
        try:
            width = int(stream["width"])
            height = int(stream["height"])
            duration = float(
                stream.get("duration") or metadata.get("format", {}).get("duration")
            )
            frame_rate = _parse_frame_rate(str(stream.get("avg_frame_rate", "0/1")))
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exception:
            raise VideoAssetValidationError(
                "video_metadata_invalid",
                "视频元数据无效",
            ) from exception
        if (
            width < 1
            or height < 1
            or duration <= 0
            or duration > max_duration_seconds
            or frame_rate <= 0
            or frame_rate > 60
        ):
            raise VideoAssetValidationError(
                "video_metadata_invalid",
                "视频尺寸、时长或帧率无效",
            )
        _decode_video(ffmpeg, path)
    return ValidatedVideo(
        data=data,
        mime_type="video/mp4",
        container="mp4",
        codec="h264",
        width=width,
        height=height,
        duration_seconds=duration,
        frame_rate=frame_rate,
        byte_size=len(data),
        sha256=sha256(data).hexdigest(),
        extension=".mp4",
    )


def extract_video_poster(data: bytes) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise VideoAssetValidationError(
            "video_decoder_unavailable",
            "视频安全解码器不可用",
        )
    with tempfile.TemporaryDirectory(prefix="office-ai-video-poster-") as directory:
        path = Path(directory) / "result.mp4"
        path.write_bytes(data)
        process = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "pipe:1",
            ],
            check=False,
            capture_output=True,
            timeout=30,
        )
    if process.returncode != 0 or not process.stdout:
        raise VideoAssetValidationError(
            "video_poster_invalid",
            "无法提取视频海报帧",
        )
    try:
        with Image.open(BytesIO(process.stdout)) as image:
            image.verify()
    except (OSError, ValueError) as exception:
        raise VideoAssetValidationError(
            "video_poster_invalid",
            "视频海报帧无效",
        ) from exception
    return process.stdout


def _probe_video(ffprobe: str, path: Path) -> dict:
    process = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if process.returncode != 0:
        raise VideoAssetValidationError("video_decode_invalid", "视频无法安全解码")
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as exception:
        raise VideoAssetValidationError(
            "video_metadata_invalid",
            "视频元数据无效",
        ) from exception
    if not isinstance(payload, dict):
        raise VideoAssetValidationError("video_metadata_invalid", "视频元数据无效")
    return payload


def _select_video_stream(metadata: dict) -> dict:
    streams = metadata.get("streams")
    if not isinstance(streams, list):
        raise VideoAssetValidationError("video_metadata_invalid", "视频元数据无效")
    video_streams = [
        item
        for item in streams
        if isinstance(item, dict)
        and item.get("codec_type") == "video"
        and item.get("disposition", {}).get("attached_pic", 0) != 1
    ]
    if len(video_streams) != 1:
        raise VideoAssetValidationError(
            "video_stream_invalid",
            "视频流数量无效",
        )
    return video_streams[0]


def _parse_frame_rate(value: str) -> float:
    numerator, denominator = value.split("/", 1)
    return int(numerator) / int(denominator)


def _decode_video(ffmpeg: str, path: Path) -> None:
    process = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-f",
            "null",
            "-",
        ],
        check=False,
        capture_output=True,
        timeout=60,
    )
    if process.returncode != 0:
        raise VideoAssetValidationError("video_decode_invalid", "视频无法安全解码")
