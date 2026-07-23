from dataclasses import dataclass
from uuid import UUID

import pytest

from app.models.file_assets import FileAsset
from app.models.users import User
from app.services.asset_contracts import AssetOperationError
from app.services.asset_management import AssetManagementService
from app.services.auth_sessions import CurrentUser
from app.services.evidence.contracts import EvidenceProcessingError
from app.services.evidence.store import EvidenceManifestStore
from app.services.file_safety.output_store import ParsedOutputStore
from app.storage.local import LocalStorageAdapter


USER_ID = UUID("019f0000-0000-7000-8000-000000000001")


@dataclass
class FakeSessions:
    async def authenticate_access(self, _access_token: str) -> CurrentUser:
        return CurrentUser(
            user_id=USER_ID,
            phone_country_code="+86",
            phone_number="13800138000",
            role="user",
            status="active",
            credit_balance=0,
            must_change_password=False,
        )


async def chunks():
    yield b"%PDF-1.7\nprivate"


@pytest.fixture
def service(session_factory, tmp_path) -> AssetManagementService:
    return AssetManagementService(
        session_factory,
        FakeSessions(),
        LocalStorageAdapter(tmp_path / "original"),
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
async def user(session_factory) -> None:
    async with session_factory() as session, session.begin():
        session.add(
            User(
                id=USER_ID,
                phone_number="13800138000",
                password_hash="hash",
            )
        )


async def upload_pdf(service: AssetManagementService, idempotency_key: str):
    return await service.upload_asset(
        access_token="user-token",
        project_id=None,
        filename="report.pdf",
        content_type="application/pdf",
        content=chunks(),
        idempotency_key=idempotency_key,
    )


async def attach_derived_outputs(service, session_factory, asset_id):
    parsed_key = service._parsed_outputs.build_key(USER_ID, asset_id)
    manifest_key = service._evidence_manifests.build_key(USER_ID, asset_id)
    parsed_path = service._parsed_outputs.resolve_asset_key(
        USER_ID, asset_id, parsed_key
    )
    manifest_path = service._evidence_manifests.resolve_asset_key(
        USER_ID, asset_id, manifest_key
    )
    for path in (parsed_path, manifest_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"private derived content")
    async with session_factory() as session, session.begin():
        stored = await session.get(FileAsset, asset_id)
        stored.parsed_storage_key = parsed_key
        stored.manifest_key = manifest_key
    return parsed_path, manifest_path


async def test_delete_removes_parsed_and_evidence_outputs_before_marking_deleted(
    service, session_factory
) -> None:
    asset = await upload_pdf(service, "derived-output-delete")
    parsed_path, manifest_path = await attach_derived_outputs(
        service, session_factory, asset.asset_id
    )

    await service.delete_asset("user-token", asset.asset_id)

    assert not parsed_path.exists()
    assert not manifest_path.exists()
    async with session_factory() as session:
        stored = await session.get(FileAsset, asset.asset_id)
    assert stored.processing_status == "deleted"
    assert stored.deleted_at is not None


@pytest.mark.parametrize("processing_status", ("scanning", "parsing"))
async def test_delete_rejects_active_worker_to_prevent_post_delete_orphans(
    service, session_factory, processing_status
) -> None:
    asset = await upload_pdf(service, f"active-{processing_status}")
    async with session_factory() as session, session.begin():
        stored = await session.get(FileAsset, asset.asset_id)
        stored.processing_status = processing_status

    with pytest.raises(AssetOperationError) as captured:
        await service.delete_asset("user-token", asset.asset_id)

    assert captured.value.error_code == "asset_processing_in_progress"
    assert captured.value.status_code == 409
    async with session_factory() as session:
        stored = await session.get(FileAsset, asset.asset_id)
    assert stored.processing_status == processing_status
    assert stored.deleted_at is None


async def test_derived_output_delete_failure_keeps_retryable_deleting_checkpoint(
    service, session_factory, monkeypatch
) -> None:
    asset = await upload_pdf(service, "derived-delete-failure")
    parsed_path, manifest_path = await attach_derived_outputs(
        service, session_factory, asset.asset_id
    )
    original_delete = service._evidence_manifests.delete

    def fail_evidence_delete(*_args):
        raise EvidenceProcessingError(
            "evidence_manifest_delete_failed", "Evidence Manifest 清理失败"
        )

    monkeypatch.setattr(service._evidence_manifests, "delete", fail_evidence_delete)
    with pytest.raises(AssetOperationError) as captured:
        await service.delete_asset("user-token", asset.asset_id)

    assert captured.value.error_code == "asset_delete_failed"
    assert not parsed_path.exists()
    assert manifest_path.exists()
    async with session_factory() as session:
        stored = await session.get(FileAsset, asset.asset_id)
    assert stored.processing_status == "deleting"
    assert stored.deleted_at is None

    monkeypatch.setattr(service._evidence_manifests, "delete", original_delete)
    await service.delete_asset("user-token", asset.asset_id)
    assert not manifest_path.exists()
