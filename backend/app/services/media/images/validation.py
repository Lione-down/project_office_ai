import base64
import unicodedata
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from PIL import Image, UnidentifiedImageError


ALLOWED_FORMATS = {
    "PNG": ("image/png", ".png"),
    "JPEG": ("image/jpeg", ".jpg"),
}

DISALLOWED_PROMPT_FRAGMENTS = (
    "child sexual",
    "child pornography",
    "csam",
    "儿童色情",
    "儿童性内容",
)


class ImageAssetValidationError(ValueError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


@dataclass(frozen=True)
class ValidatedImage:
    data: bytes
    mime_type: str
    extension: str
    byte_size: int
    sha256: str
    width: int
    height: int


def validate_image_prompt_policy(prompt: str) -> None:
    normalized = " ".join(unicodedata.normalize("NFKC", prompt).casefold().split())
    if any(fragment in normalized for fragment in DISALLOWED_PROMPT_FRAGMENTS):
        raise ImageAssetValidationError(
            "image_content_policy_rejected",
            "图片 Prompt 不符合内容安全要求",
        )


def validate_image_bytes(
    data: bytes,
    *,
    max_bytes: int,
    max_decoded_bytes: int,
) -> ValidatedImage:
    if not data or len(data) > max_bytes:
        raise ImageAssetValidationError(
            "image_size_invalid",
            "图片容量不符合要求",
        )
    try:
        with Image.open(BytesIO(data)) as probe:
            image_format = probe.format
            probe.verify()
        if image_format not in ALLOWED_FORMATS:
            raise ImageAssetValidationError(
                "image_format_invalid",
                "图片格式不受支持",
            )
        with Image.open(BytesIO(data)) as decoded:
            decoded.load()
            width, height = decoded.size
            channels = len(decoded.getbands())
    except ImageAssetValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exception:
        raise ImageAssetValidationError(
            "image_decode_invalid",
            "图片无法完整解码",
        ) from exception
    if (
        width < 1
        or height < 1
        or width > 8192
        or height > 8192
        or width * height * max(4, channels) > max_decoded_bytes
    ):
        raise ImageAssetValidationError(
            "image_dimensions_invalid",
            "图片尺寸不符合要求",
        )
    mime_type, extension = ALLOWED_FORMATS[image_format]
    return ValidatedImage(
        data=data,
        mime_type=mime_type,
        extension=extension,
        byte_size=len(data),
        sha256=sha256(data).hexdigest(),
        width=width,
        height=height,
    )


def image_data_uri(image: ValidatedImage) -> str:
    return f"data:{image.mime_type};base64," + base64.b64encode(image.data).decode(
        "ascii"
    )
