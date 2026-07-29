import base64
from io import BytesIO

from PIL import Image
import pytest

from app.services.media.images.validation import (
    ImageAssetValidationError,
    image_data_uri,
    validate_image_bytes,
    validate_image_prompt_policy,
)


def png_bytes(width: int = 32, height: int = 18) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(16, 64, 128)).save(
        buffer,
        format="PNG",
    )
    return buffer.getvalue()


def test_image_validation_uses_fully_decoded_bytes_and_authoritative_dimensions() -> (
    None
):
    payload = png_bytes()
    validated = validate_image_bytes(
        payload,
        max_bytes=20 * 1024 * 1024,
        max_decoded_bytes=128 * 1024 * 1024,
    )

    assert validated.mime_type == "image/png"
    assert validated.width == 32
    assert validated.height == 18
    assert validated.byte_size == len(payload)
    assert validated.sha256
    assert image_data_uri(validated) == (
        "data:image/png;base64," + base64.b64encode(payload).decode("ascii")
    )


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"\x89PNG\r\n\x1a\nnot-a-decoded-image",
        b"<svg onload='alert(1)'/>",
    ],
)
def test_image_validation_fails_closed_for_empty_truncated_or_active_content(
    payload: bytes,
) -> None:
    with pytest.raises(ImageAssetValidationError):
        validate_image_bytes(
            payload,
            max_bytes=20 * 1024 * 1024,
            max_decoded_bytes=128 * 1024 * 1024,
        )


def test_image_prompt_policy_rejects_high_confidence_disallowed_content() -> None:
    with pytest.raises(ImageAssetValidationError) as caught:
        validate_image_prompt_policy("Create CHILD   sexual content")

    assert caught.value.error_code == "image_content_policy_rejected"
