from hashlib import sha256
from pathlib import Path
from uuid import UUID

from PIL import Image
from sqlalchemy import select

from app.models.file_assets import FileAsset
from app.models.projects import Project
from app.services.evidence.builder import EvidenceManifestBuilder
from app.services.evidence.store import EvidenceManifestStore
from app.services.file_safety.clamav import ScanResult
from app.services.file_safety.contracts import ProcessingLimits
from app.services.file_safety.output_store import ParsedOutputStore
from app.services.file_safety.parsers import SafeDocumentParser
from app.services.ocr.contracts import OcrServiceError
from app.storage.local import LocalStorageAdapter
from app.workers.asset_processing.service import AssetProcessingService


USER_ID = UUID("019f0000-0000-7000-8000-000000000031")


class CleanScanner:
    async def scan(self, _path: Path) -> ScanResult:
        return ScanResult(is_clean=True)


class NeverCalledOcr:
    async def recognize(self, *_args, **_kwargs):
        raise AssertionError("OCR must not run for parsed text")


class UnavailableOcr:
    async def recognize(self, *_args, **_kwargs):
        raise OcrServiceError("ocr_unavailable", "OCR 服务暂时不可用", retryable=True)


async def create_asset(
    session_factory,
    storage: LocalStorageAdapter,
    *,
    asset_id: UUID,
    filename: str,
    mime_type: str,
    payload: bytes,
) -> FileAsset:
    project = Project(user_id=USER_ID, name="证据处理")
    extension = Path(filename).suffix
    asset = FileAsset(
        id=asset_id,
        user_id=USER_ID,
        project_id=project.id,
        original_filename=filename,
        file_category="image" if mime_type.startswith("image/") else "text",
        mime_type=mime_type,
        byte_size=len(payload),
        sha256=sha256(payload).hexdigest(),
        storage_provider="local",
        storage_key=storage.build_quarantine_key(USER_ID, asset_id, extension),
        processing_status="quarantined",
        idempotency_key=f"evidence-{asset_id}",
    )
    path = storage.resolve_asset_key(USER_ID, asset.id, asset.storage_key)
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)
    async with session_factory() as session:
        session.add_all((project, asset))
        await session.commit()
    return asset


def worker(
    session_factory,
    storage: LocalStorageAdapter,
    parsed_store: ParsedOutputStore,
    manifest_store: EvidenceManifestStore,
    ocr_client,
) -> AssetProcessingService:
    limits = ProcessingLimits()
    return AssetProcessingService(
        session_factory,
        storage,
        parsed_store,
        CleanScanner(),
        SafeDocumentParser(limits),
        limits,
        evidence_builder=EvidenceManifestBuilder(ocr_client),
        manifest_store=manifest_store,
        ocr_retry_limit=3,
        ocr_retry_backoff_seconds=30,
    )


async def test_asset_is_ready_only_after_valid_manifest_is_persisted(
    session_factory, tmp_path: Path
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    asset_id = UUID("019f0000-0000-7000-8000-000000000032")
    asset = await create_asset(
        session_factory,
        storage,
        asset_id=asset_id,
        filename="notes.txt",
        mime_type="text/plain",
        payload=b"Revenue is stable",
    )
    parsed_store = ParsedOutputStore(tmp_path / "parsed", max_output_bytes=4096)
    manifest_store = EvidenceManifestStore(tmp_path / "evidence", max_output_bytes=4096)

    processed = await worker(
        session_factory,
        storage,
        parsed_store,
        manifest_store,
        NeverCalledOcr(),
    ).process(asset.id)

    async with session_factory() as session:
        stored = await session.scalar(select(FileAsset).where(FileAsset.id == asset.id))
    assert processed is True
    assert stored.processing_status == "ready"
    assert stored.manifest_status == "valid"
    assert stored.manifest_schema_version == "evidence-manifest.v1"
    assert stored.manifest_sha256
    assert stored.evidence_engine_version == "1.0.0"
    assert stored.evidence_warning_count == 0
    assert stored.evidence_blocker_count == 0
    assert stored.evidence_generated_at is not None
    assert manifest_store.resolve_asset_key(
        USER_ID, asset.id, stored.manifest_key
    ).is_file()


async def test_temporary_ocr_failure_is_retryable_and_never_marks_asset_ready(
    session_factory, tmp_path: Path
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    image_path = tmp_path / "source.png"
    Image.new("RGB", (4, 4), color="white").save(image_path)
    payload = image_path.read_bytes()
    asset = await create_asset(
        session_factory,
        storage,
        asset_id=UUID("019f0000-0000-7000-8000-000000000033"),
        filename="chart.png",
        mime_type="image/png",
        payload=payload,
    )
    manifest_store = EvidenceManifestStore(tmp_path / "evidence", max_output_bytes=4096)

    await worker(
        session_factory,
        storage,
        ParsedOutputStore(tmp_path / "parsed", max_output_bytes=4096),
        manifest_store,
        UnavailableOcr(),
    ).process(asset.id)

    async with session_factory() as session:
        stored = await session.scalar(select(FileAsset).where(FileAsset.id == asset.id))
    assert stored.processing_status == "quarantined"
    assert stored.processing_error_code == "ocr_unavailable"
    assert stored.processing_error_message == "OCR 服务暂时不可用"
    assert stored.processing_retry_count == 1
    assert stored.processing_retry_after is not None
    assert stored.manifest_status == "retryable_error"
    assert stored.manifest_sha256 is None
    assert stored.evidence_generated_at is None
    assert stored.processed_at is None
    assert not (tmp_path / "evidence").exists()
