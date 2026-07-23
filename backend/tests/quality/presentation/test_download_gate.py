from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, FileAsset, Project, User
from app.services.asset_contracts import AssetOperationError
from app.services.asset_management import AssetManagementService
from app.services.auth_sessions import CurrentUser
from app.storage.local import LocalStorageAdapter


USER_ID = UUID("019b0000-0000-7000-8000-000000000341")
PROJECT_ID = UUID("019b0000-0000-7000-8000-000000000342")
ASSET_ID = UUID("019b0000-0000-7000-8000-000000000343")
TASK_ID = UUID("019b0000-0000-7000-8000-000000000344")


@dataclass
class FakeSessions:
    async def authenticate_access(self, access_token: str) -> CurrentUser:
        assert access_token == "token"
        return CurrentUser(
            user_id=USER_ID,
            phone_country_code="+86",
            phone_number="13800000341",
            role="user",
            status="active",
            credit_balance=0,
            must_change_password=False,
        )


async def build_service(tmp_path: Path, quality_status: str | None):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    root = tmp_path / "files"
    original = (
        root / "users" / str(USER_ID) / "outputs" / str(ASSET_ID) / "presentation.pptx"
    )
    repaired = original.parent / "quality" / "repaired.pptx"
    repaired.parent.mkdir(parents=True)
    original.write_bytes(b"original")
    repaired.write_bytes(b"validated-repaired")
    async with session_factory() as session, session.begin():
        session.add_all(
            [
                User(
                    id=USER_ID,
                    phone_number="13800000341",
                    password_hash="hash",
                ),
                Project(
                    id=PROJECT_ID,
                    user_id=USER_ID,
                    name="Quality download",
                    is_default=False,
                ),
                FileAsset(
                    id=ASSET_ID,
                    user_id=USER_ID,
                    project_id=PROJECT_ID,
                    original_filename="sales-presentation.pptx",
                    file_category="presentation",
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "presentationml.presentation"
                    ),
                    byte_size=original.stat().st_size,
                    sha256=sha256(original.read_bytes()).hexdigest(),
                    storage_provider="local",
                    storage_key=(
                        f"users/{USER_ID}/outputs/{ASSET_ID}/presentation.pptx"
                    ),
                    processing_status="ready",
                    generated_task_id=TASK_ID,
                    quality_status=quality_status,
                    quality_validated_key=(
                        f"users/{USER_ID}/outputs/{ASSET_ID}/quality/repaired.pptx"
                        if quality_status == "passed_with_warnings"
                        else None
                    ),
                    quality_validated_sha256=(
                        sha256(repaired.read_bytes()).hexdigest()
                        if quality_status == "passed_with_warnings"
                        else None
                    ),
                    quality_validated_byte_size=(
                        repaired.stat().st_size
                        if quality_status == "passed_with_warnings"
                        else None
                    ),
                    processing_warnings=[],
                ),
            ]
        )
    service = AssetManagementService(
        session_factory,
        FakeSessions(),
        LocalStorageAdapter(root),
        max_file_bytes=1024,
        max_image_bytes=1024,
    )
    return service, repaired, engine


@pytest.mark.parametrize(
    ("quality_status", "error_code"),
    [(None, "asset_quality_pending"), ("blocked", "asset_quality_blocked")],
)
async def test_generated_presentation_download_requires_quality_pass(
    tmp_path: Path, quality_status: str | None, error_code: str
) -> None:
    service, _repaired, engine = await build_service(tmp_path, quality_status)
    try:
        with pytest.raises(AssetOperationError) as captured:
            await service.open_asset("token", ASSET_ID)
    finally:
        await engine.dispose()

    assert captured.value.error_code == error_code
    assert captured.value.status_code == 409


async def test_download_uses_repaired_validated_artifact_and_checks_integrity(
    tmp_path: Path,
) -> None:
    service, repaired, engine = await build_service(tmp_path, "passed_with_warnings")
    try:
        content = await service.open_asset("token", ASSET_ID)
        assert content.path == repaired
        assert content.path.read_bytes() == b"validated-repaired"

        repaired.write_bytes(b"tampered")
        with pytest.raises(AssetOperationError) as captured:
            await service.open_asset("token", ASSET_ID)
    finally:
        await engine.dispose()

    assert captured.value.error_code == "asset_quality_integrity_failed"
    assert captured.value.status_code == 409
