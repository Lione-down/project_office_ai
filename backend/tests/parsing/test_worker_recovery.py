from datetime import timedelta

import pytest

from app.models.base import utc_now
from app.models.file_assets import FileAsset
from app.services.evidence.builder import EvidenceManifestBuilder
from app.services.evidence.store import EvidenceManifestStore
from app.services.file_safety.contracts import ProcessingLimits
from app.services.file_safety.output_store import ParsedOutputStore
from app.services.file_safety.parsers import SafeDocumentParser
from app.storage.local import LocalStorageAdapter
from tests.parsing.test_worker import (
    CleanupFailingStore,
    CompletionFailingService,
    HardCrashAfterOutputService,
    NeverCalledOcr,
    RecordingCleanScanner,
    SimulatedHardCrash,
    USER_ID,
    create_asset,
    load_asset,
)


async def test_output_cleanup_failure_keeps_durable_recovery_key(
    session_factory, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    asset = await create_asset(session_factory, storage)
    output_store = CleanupFailingStore(tmp_path / "output", max_output_bytes=1024)
    worker = CompletionFailingService(
        session_factory,
        storage,
        output_store,
        RecordingCleanScanner(session_factory),
        SafeDocumentParser(ProcessingLimits()),
        ProcessingLimits(),
        evidence_builder=EvidenceManifestBuilder(NeverCalledOcr()),
        manifest_store=EvidenceManifestStore(
            tmp_path / "evidence", max_output_bytes=64 * 1024
        ),
        ocr_retry_limit=3,
        ocr_retry_backoff_seconds=30,
    )

    await worker.process(asset.id)
    stored = await load_asset(session_factory, asset.id)

    assert stored.processing_status == "rejected"
    assert stored.processing_error_code == "processing_state_conflict"
    assert stored.processing_warnings == ["parsed_output_cleanup_failed"]
    assert stored.parsed_storage_key == output_store.build_key(USER_ID, asset.id)
    assert output_store.resolve_asset_key(
        USER_ID, asset.id, stored.parsed_storage_key
    ).is_file()


async def test_hard_crash_after_output_keeps_durable_deterministic_recovery_key(
    session_factory, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    asset = await create_asset(session_factory, storage)
    output_store = ParsedOutputStore(tmp_path / "output", max_output_bytes=1024)
    worker = HardCrashAfterOutputService(
        session_factory,
        storage,
        output_store,
        RecordingCleanScanner(session_factory),
        SafeDocumentParser(ProcessingLimits()),
        ProcessingLimits(processing_lease_seconds=1),
        evidence_builder=EvidenceManifestBuilder(NeverCalledOcr()),
        manifest_store=EvidenceManifestStore(
            tmp_path / "evidence", max_output_bytes=64 * 1024
        ),
        ocr_retry_limit=3,
        ocr_retry_backoff_seconds=30,
    )

    with pytest.raises(SimulatedHardCrash):
        await worker.process(asset.id)

    crashed = await load_asset(session_factory, asset.id)
    expected_key = output_store.build_key(USER_ID, asset.id)
    assert crashed.processing_status == "parsing"
    assert crashed.parsed_storage_key == expected_key
    assert output_store.resolve_asset_key(USER_ID, asset.id, expected_key).is_file()

    async with session_factory() as session:
        stored = await session.get(FileAsset, asset.id)
        stored.processing_started_at = utc_now() - timedelta(minutes=1)
        await session.commit()
    await worker.reconcile_stale_leases()
    reconciled = await load_asset(session_factory, asset.id)

    assert reconciled.processing_status == "rejected"
    assert reconciled.manifest_status == "invalid"
    assert reconciled.processing_error_code == "processing_lease_expired"
    assert reconciled.parsed_storage_key == expected_key
    assert output_store.resolve_asset_key(USER_ID, asset.id, expected_key).is_file()
