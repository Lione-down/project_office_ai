import asyncio
from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.audit_logs import AuditLog
from app.models.file_assets import FileAsset
from app.models.projects import Project
from app.models.users import User
from app.services.asset_management import (
    AssetAuditContext,
    AssetManagementService,
    AssetOperationError,
)
from app.services.auth_sessions import CurrentUser
from app.services.evidence.store import EvidenceManifestStore
from app.services.file_safety.output_store import ParsedOutputStore
from app.storage.local import LocalStorageAdapter, StorageOperationError


USER_ID = UUID("019f0000-0000-7000-8000-000000000001")
OTHER_USER_ID = UUID("019f0000-0000-7000-8000-000000000002")
ADMIN_ID = UUID("019f0000-0000-7000-8000-000000000003")


@dataclass
class FakeSessions:
    async def authenticate_access(self, access_token: str) -> CurrentUser:
        identities = {
            "user-token": (USER_ID, "user"),
            "other-token": (OTHER_USER_ID, "user"),
            "admin-token": (ADMIN_ID, "admin"),
        }
        user_id, role = identities[access_token]
        return CurrentUser(
            user_id=user_id,
            phone_country_code="+86",
            phone_number="13800138000",
            role=role,
            status="active",
            credit_balance=0,
            must_change_password=False,
        )


async def chunks(*values: bytes):
    for value in values:
        yield value


async def unread_chunks():
    raise AssertionError("幂等重放不应再次读取上传内容")
    yield b"unreachable"


@pytest.fixture
def service(session_factory, tmp_path) -> AssetManagementService:
    return AssetManagementService(
        session_factory,
        FakeSessions(),
        LocalStorageAdapter(tmp_path),
        max_file_bytes=1024,
        max_image_bytes=512,
        parsed_outputs=ParsedOutputStore(
            tmp_path / "parsed", max_output_bytes=1024 * 1024
        ),
        evidence_manifests=EvidenceManifestStore(
            tmp_path / "evidence", max_output_bytes=1024 * 1024
        ),
    )


@pytest.fixture(autouse=True)
async def users(session_factory) -> None:
    async with session_factory() as session, session.begin():
        session.add_all(
            (
                User(
                    id=USER_ID,
                    phone_number="13800138000",
                    password_hash="hash",
                ),
                User(
                    id=OTHER_USER_ID,
                    phone_number="13800138001",
                    password_hash="hash",
                ),
                User(
                    id=ADMIN_ID,
                    phone_number="13800138002",
                    password_hash="hash",
                    role="admin",
                ),
            )
        )


async def upload_pdf(
    service: AssetManagementService,
    *,
    token: str = "user-token",
    idempotency_key: str = "upload-1",
):
    return await service.upload_asset(
        access_token=token,
        project_id=None,
        filename="report.pdf",
        content_type="application/pdf",
        content=chunks(b"%PDF-1.7\n", b"safe"),
        idempotency_key=idempotency_key,
    )


async def test_upload_creates_default_project_and_quarantined_asset(service) -> None:
    asset = await upload_pdf(service)
    projects = await service.list_projects("user-token")

    assert len(projects) == 1
    assert projects[0].is_default is True
    assert asset.project_id == projects[0].project_id
    assert asset.processing_status == "quarantined"
    assert asset.original_filename == "report.pdf"
    assert asset.byte_size == len(b"%PDF-1.7\nsafe")
    assert not hasattr(asset, "storage_key")


async def test_upload_replay_returns_existing_asset_without_reading_content(
    service,
) -> None:
    first = await upload_pdf(service, idempotency_key="same-request")

    replay = await service.upload_asset(
        access_token="user-token",
        project_id=first.project_id,
        filename="different.pdf",
        content_type="application/pdf",
        content=unread_chunks(),
        idempotency_key="same-request",
    )

    assert replay.asset_id == first.asset_id
    assert replay.sha256 == first.sha256


async def test_user_asset_access_is_owner_scoped_and_admin_read_is_audited(
    service, session_factory
) -> None:
    asset = await upload_pdf(service)

    with pytest.raises(AssetOperationError) as captured:
        await service.get_asset("other-token", asset.asset_id)
    assert captured.value.error_code == "asset_not_found"
    with pytest.raises(AssetOperationError) as captured:
        await service.open_asset("other-token", asset.asset_id)
    assert captured.value.status_code == 404

    opened = await service.admin_open_asset(
        access_token="admin-token",
        asset_id=asset.asset_id,
        reason="support investigation",
        audit=AssetAuditContext("127.0.0.1", "pytest", "trace-asset-admin"),
    )

    assert opened.path.read_bytes().startswith(b"%PDF")
    async with session_factory() as session:
        audit = await session.scalar(
            select(AuditLog).where(AuditLog.action == "asset.admin_read")
        )
    assert audit is not None
    assert audit.actor_user_id == ADMIN_ID
    assert audit.target_id == asset.asset_id
    assert audit.result == "success"
    assert "storage_key" not in audit.context


async def test_upload_sanitizes_filename_and_rejects_mime_or_signature_mismatch(
    service,
) -> None:
    created = await service.upload_asset(
        access_token="user-token",
        project_id=None,
        filename="../控制\x00报告.txt",
        content_type="text/plain; charset=utf-8",
        content=chunks("内容".encode()),
        idempotency_key="safe-name",
    )
    assert created.original_filename == "控制报告.txt"

    with pytest.raises(AssetOperationError) as captured:
        await service.upload_asset(
            access_token="user-token",
            project_id=None,
            filename="fake.pdf",
            content_type="image/png",
            content=chunks(b"not a pdf"),
            idempotency_key="mime-mismatch",
        )
    assert captured.value.error_code == "file_mime_mismatch"

    with pytest.raises(AssetOperationError) as captured:
        await service.upload_asset(
            access_token="user-token",
            project_id=None,
            filename="fake.pdf",
            content_type="application/pdf",
            content=chunks(b"not a pdf"),
            idempotency_key="signature-mismatch",
        )
    assert captured.value.error_code == "file_signature_invalid"


async def test_delete_checks_references_then_removes_only_owned_asset(
    service, session_factory
) -> None:
    parent = await upload_pdf(service, idempotency_key="parent")
    child = await upload_pdf(service, idempotency_key="child")
    async with session_factory() as session, session.begin():
        stored_child = await session.get(FileAsset, child.asset_id)
        stored_child.parent_asset_id = parent.asset_id

    with pytest.raises(AssetOperationError) as captured:
        await service.delete_asset("user-token", parent.asset_id)
    assert captured.value.error_code == "asset_in_use"

    await service.delete_asset("user-token", child.asset_id)
    await service.delete_asset("user-token", parent.asset_id)

    with pytest.raises(AssetOperationError):
        await service.get_asset("user-token", parent.asset_id)
    with pytest.raises(AssetOperationError):
        await service.get_asset("user-token", child.asset_id)


async def test_project_update_service_rejects_explicit_null(service) -> None:
    project = await service.create_project("user-token", "经营分析")

    for changes in ({"name": None}, {"is_archived": None}):
        with pytest.raises(AssetOperationError) as captured:
            await service.update_project("user-token", project.project_id, changes)
        assert captured.value.error_code == "project_update_invalid"
        assert captured.value.status_code == 422


async def test_upload_revalidates_project_after_file_write(
    service, session_factory, monkeypatch, tmp_path
) -> None:
    project = await service.create_project("user-token", "经营分析")
    original_write = service._storage.write_quarantine

    async def write_then_archive(**kwargs):
        stored = await original_write(**kwargs)
        async with session_factory() as session, session.begin():
            persisted = await session.get(Project, project.project_id)
            persisted.is_archived = True
        return stored

    monkeypatch.setattr(service._storage, "write_quarantine", write_then_archive)

    with pytest.raises(AssetOperationError) as captured:
        await service.upload_asset(
            access_token="user-token",
            project_id=project.project_id,
            filename="report.pdf",
            content_type="application/pdf",
            content=chunks(b"%PDF-1.7\nsafe"),
            idempotency_key="project-state-race",
        )

    assert captured.value.error_code == "project_archived"
    async with session_factory() as session:
        assert await session.scalar(select(FileAsset.id)) is None
    assert not list(tmp_path.rglob("original.pdf"))


async def test_concurrent_uploads_share_one_default_project(tmp_path) -> None:
    database_path = tmp_path / "default-project-race.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    rendezvous = asyncio.Barrier(2)

    class RacingSession(AsyncSession):
        async def scalar(self, statement, *args, **kwargs):
            result = await super().scalar(statement, *args, **kwargs)
            if (
                result is None
                and "projects.is_default IS true" in str(statement)
                and "projects.deleted_at IS NULL" in str(statement)
            ):
                await self.rollback()
                await rendezvous.wait()
            return result

    factory = async_sessionmaker(engine, class_=RacingSession, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session, session.begin():
        session.add(User(id=USER_ID, phone_number="13800138000", password_hash="hash"))

    racing_service = AssetManagementService(
        factory,
        FakeSessions(),
        LocalStorageAdapter(tmp_path / "files"),
        max_file_bytes=1024,
        max_image_bytes=512,
    )
    try:
        first, second = await asyncio.gather(
            upload_pdf(racing_service, idempotency_key="concurrent-1"),
            upload_pdf(racing_service, idempotency_key="concurrent-2"),
        )
        async with factory() as session:
            defaults = (
                await session.scalars(
                    select(Project).where(
                        Project.user_id == USER_ID,
                        Project.is_default.is_(True),
                        Project.deleted_at.is_(None),
                    )
                )
            ).all()
    finally:
        await engine.dispose()

    assert len(defaults) == 1
    assert first.project_id == defaults[0].id
    assert second.project_id == defaults[0].id


async def test_upload_commit_failure_removes_quarantine_file(
    service, session_factory, tmp_path
) -> None:
    project = await service.create_project("user-token", "经营分析")

    def fail_asset_insert(*_args):
        raise RuntimeError("database commit failed")

    event.listen(FileAsset, "before_insert", fail_asset_insert)
    try:
        with pytest.raises(RuntimeError, match="database commit failed"):
            await service.upload_asset(
                access_token="user-token",
                project_id=project.project_id,
                filename="report.pdf",
                content_type="application/pdf",
                content=chunks(b"%PDF-1.7\nsafe"),
                idempotency_key="commit-failure",
            )
    finally:
        event.remove(FileAsset, "before_insert", fail_asset_insert)

    async with session_factory() as session:
        assert await session.scalar(select(FileAsset.id)) is None
    assert not list(tmp_path.rglob("original.pdf"))


async def test_upload_preserves_quarantine_cleanup_failure(
    service, monkeypatch
) -> None:
    project = await service.create_project("user-token", "经营分析")

    async def fail_write(**_kwargs):
        raise StorageOperationError(
            "quarantine_cleanup_failed", "上传暂存文件清理失败", 500
        )

    def fail_second_cleanup(*_args):
        raise StorageOperationError("asset_delete_failed", "资产文件删除失败", 500)

    monkeypatch.setattr(service._storage, "write_quarantine", fail_write)
    monkeypatch.setattr(service._storage, "delete_asset", fail_second_cleanup)

    with pytest.raises(AssetOperationError) as captured:
        await service.upload_asset(
            access_token="user-token",
            project_id=project.project_id,
            filename="report.pdf",
            content_type="application/pdf",
            content=chunks(b"%PDF-1.7\nsafe"),
            idempotency_key="cleanup-failure",
        )

    assert captured.value.error_code == "quarantine_cleanup_failed"
    assert captured.value.status_code == 500


async def test_upload_persists_uploaded_checkpoint_before_reading_stream(
    service, session_factory
) -> None:
    project = await service.create_project("user-token", "经营分析")
    observed_statuses: list[str] = []

    async def inspecting_chunks():
        async with session_factory() as session:
            checkpoint = await session.scalar(
                select(FileAsset).where(
                    FileAsset.user_id == USER_ID,
                    FileAsset.idempotency_key == "checkpoint-before-stream",
                )
            )
        assert checkpoint is not None
        observed_statuses.append(checkpoint.processing_status)
        yield b"%PDF-1.7\nsafe"

    created = await service.upload_asset(
        access_token="user-token",
        project_id=project.project_id,
        filename="report.pdf",
        content_type="application/pdf",
        content=inspecting_chunks(),
        idempotency_key="checkpoint-before-stream",
    )

    assert observed_statuses == ["uploaded"]
    assert created.processing_status == "quarantined"


async def test_signature_cleanup_failure_keeps_tracked_deleting_asset(
    service, session_factory, monkeypatch
) -> None:
    project = await service.create_project("user-token", "经营分析")

    def fail_cleanup(*_args):
        raise StorageOperationError("asset_delete_failed", "资产文件删除失败", 500)

    monkeypatch.setattr(service._storage, "delete_asset", fail_cleanup)

    with pytest.raises(AssetOperationError) as captured:
        await service.upload_asset(
            access_token="user-token",
            project_id=project.project_id,
            filename="report.pdf",
            content_type="application/pdf",
            content=chunks(b"not-a-pdf"),
            idempotency_key="signature-cleanup-failure",
        )

    assert captured.value.error_code == "file_signature_invalid"
    assert any(
        "cleanup failed: StorageOperationError" in note
        for note in captured.value.__notes__
    )
    async with session_factory() as session:
        tracked = await session.scalar(
            select(FileAsset).where(
                FileAsset.idempotency_key == "signature-cleanup-failure"
            )
        )
    assert tracked is not None
    assert tracked.processing_status == "deleting"


@pytest.mark.parametrize("failure", (asyncio.CancelledError(), RuntimeError("failed")))
async def test_finalization_failure_leaves_file_tracked_by_uploaded_checkpoint(
    failure, service, session_factory, tmp_path
) -> None:
    project = await service.create_project("user-token", "经营分析")

    def fail_finalization(*_args):
        raise failure

    event.listen(FileAsset, "before_update", fail_finalization)
    try:
        with pytest.raises(type(failure)):
            await service.upload_asset(
                access_token="user-token",
                project_id=project.project_id,
                filename="report.pdf",
                content_type="application/pdf",
                content=chunks(b"%PDF-1.7\ntracked"),
                idempotency_key=f"finalize-{type(failure).__name__}",
            )
    finally:
        event.remove(FileAsset, "before_update", fail_finalization)

    async with session_factory() as session:
        checkpoint = await session.scalar(
            select(FileAsset).where(
                FileAsset.idempotency_key == f"finalize-{type(failure).__name__}"
            )
        )
    assert checkpoint is not None
    assert checkpoint.processing_status == "uploaded"
    assert list(tmp_path.rglob("original.pdf"))
