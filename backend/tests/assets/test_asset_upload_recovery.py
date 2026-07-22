import asyncio
from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import new_uuid7
from app.models.file_assets import FileAsset
from app.models.users import User
from app.services.asset_management import AssetManagementService
from app.services.auth_sessions import CurrentUser
from app.storage.local import LocalStorageAdapter


USER_ID = UUID("019f0000-0000-7000-8000-000000000001")


@dataclass
class FakeSessions:
    async def authenticate_access(self, access_token: str) -> CurrentUser:
        assert access_token == "user-token"
        return CurrentUser(
            user_id=USER_ID,
            phone_country_code="+86",
            phone_number="13800138000",
            role="user",
            status="active",
            credit_balance=0,
            must_change_password=False,
        )


@pytest.fixture
def service(session_factory, tmp_path) -> AssetManagementService:
    return AssetManagementService(
        session_factory,
        FakeSessions(),
        LocalStorageAdapter(tmp_path),
        max_file_bytes=1024,
        max_image_bytes=512,
    )


@pytest.fixture(autouse=True)
async def user(session_factory) -> None:
    async with session_factory() as session, session.begin():
        session.add(
            User(
                id=USER_ID,
                phone_number="13800138000",
                password_hash="hash",
            )
        )


async def test_cancelled_stream_cleanup_failure_keeps_original_and_checkpoint(
    service, session_factory, monkeypatch, tmp_path
) -> None:
    project = await service.create_project("user-token", "经营分析")

    async def cancelled_chunks():
        yield b"partial-cancelled-content"
        raise asyncio.CancelledError()

    def fail_cleanup(_path):
        raise PermissionError("directory is locked")

    monkeypatch.setattr("app.storage.local.shutil.rmtree", fail_cleanup)

    with pytest.raises(asyncio.CancelledError) as captured:
        await service.upload_asset(
            access_token="user-token",
            project_id=project.project_id,
            filename="report.pdf",
            content_type="application/pdf",
            content=cancelled_chunks(),
            idempotency_key="cancel-cleanup-failure",
        )

    assert any(
        "cleanup failed: PermissionError" in note for note in captured.value.__notes__
    )
    async with session_factory() as session:
        tracked = await session.scalar(
            select(FileAsset).where(
                FileAsset.idempotency_key == "cancel-cleanup-failure"
            )
        )
    assert tracked is not None
    assert tracked.processing_status == "deleting"
    assert list(tmp_path.rglob("original.pdf"))


@pytest.mark.parametrize(
    "primary_error",
    (RuntimeError("finalization failed"), asyncio.CancelledError()),
)
async def test_finalization_rollback_failure_preserves_primary_with_safe_recovery_note(
    service, session_factory, monkeypatch, primary_error
) -> None:
    project = await service.create_project("user-token", "经营分析")
    asset_id = new_uuid7()
    async with session_factory() as session, session.begin():
        session.add(
            FileAsset(
                id=asset_id,
                user_id=USER_ID,
                project_id=project.project_id,
                original_filename="report.pdf",
                file_category="document",
                mime_type="application/pdf",
                byte_size=0,
                sha256="0" * 64,
                storage_provider="local",
                storage_key=(f"users/{USER_ID}/quarantine/{asset_id}/original.pdf"),
                processing_status="uploaded",
                idempotency_key=f"rollback-{type(primary_error).__name__}",
            )
        )

    async def fail_commit(_session) -> None:
        raise primary_error

    async def fail_rollback(_session) -> None:
        raise OSError("C:/secret/files/database connection detail")

    monkeypatch.setattr(AsyncSession, "commit", fail_commit)
    monkeypatch.setattr(AsyncSession, "rollback", fail_rollback)

    with pytest.raises(type(primary_error)) as captured:
        await service._uploads._finalize_checkpoint(
            asset_id,
            USER_ID,
            project.project_id,
            128,
            "a" * 64,
        )

    assert captured.value is primary_error
    assert captured.value.recovery_failure is True
    assert captured.value.__notes__ == [
        "checkpoint finalization rollback failed: OSError"
    ]
