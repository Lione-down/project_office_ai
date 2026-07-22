from pathlib import Path

import pytest
from pydantic import ValidationError

from app.settings.config import Settings


def test_asset_storage_settings_have_safe_defaults_and_environment_aliases() -> None:
    defaults = Settings()
    configured = Settings(
        OFFICE_AI_FILES_ROOT="D:/controlled/office-ai-files",
        OFFICE_AI_MAX_FILE_BYTES=1234,
        OFFICE_AI_MAX_IMAGE_BYTES=456,
    )

    assert defaults.files_root == Path("/app/files")
    assert defaults.max_file_bytes == 50 * 1024 * 1024
    assert defaults.max_upload_body_bytes == 50 * 1024 * 1024 + 64 * 1024
    assert defaults.max_image_bytes == 20 * 1024 * 1024
    assert configured.files_root == Path("D:/controlled/office-ai-files")
    assert configured.max_file_bytes == 1234
    assert configured.max_upload_body_bytes == 1234 + 64 * 1024
    assert configured.max_image_bytes == 456


def test_asset_size_settings_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(OFFICE_AI_MAX_FILE_BYTES=0)
