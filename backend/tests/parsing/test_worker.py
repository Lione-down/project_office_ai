import asyncio
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import time
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.models.credit_ledger import CreditLedger
from app.models.file_assets import FileAsset
from app.models.projects import Project
from app.models.base import utc_now
from app.services.file_safety.clamav import ScanResult
from app.services.file_safety.contracts import FileSafetyError, ProcessingLimits
from app.services.file_safety.output_store import ParsedOutputStore
from app.services.file_safety.parsers import SafeDocumentParser
from app.schemas.assets import AssetResponse
from app.services.asset_contracts import asset_summary
from app.storage.local import LocalStorageAdapter
from app.workers.asset_processing.service import AssetProcessingService


USER_ID = UUID("019f0000-0000-7000-8000-000000000001")


class RecordingCleanScanner:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.statuses = []
        self.calls = 0

    async def scan(self, path: Path) -> ScanResult:
        self.calls += 1
        async with self.session_factory() as session:
            status = await session.scalar(
                select(FileAsset.processing_status).where(
                    FileAsset.storage_key.like("%original.txt")
                )
            )
            self.statuses.append(status)
        return ScanResult(is_clean=True)


class FailingScanner:
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        self.calls = 0

    async def scan(self, path: Path) -> ScanResult:
        self.calls += 1
        raise FileSafetyError(self.error_code, "文件未通过安全扫描")


class ExplodingParser:
    def __init__(self, exception: Exception) -> None:
        self.exception = exception
        self.calls = 0

    def parse(self, descriptor):
        self.calls += 1
        raise self.exception


class SlowEscapingParser:
    def __init__(self, marker_path: Path, delay_seconds: float) -> None:
        self.marker_path = marker_path
        self.delay_seconds = delay_seconds

    def parse(self, descriptor):
        time.sleep(self.delay_seconds)
        self.marker_path.write_text("escaped", encoding="utf-8")
        return SafeDocumentParser(ProcessingLimits()).parse(descriptor)


class SlowScanner:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def scan(self, path: Path) -> ScanResult:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return ScanResult(is_clean=True)


class CleanupFailingStore(ParsedOutputStore):
    def delete(self, user_id, asset_id, storage_key) -> None:
        raise FileSafetyError("parsed_output_delete_failed", "解析结果清理失败")


class CompletionFailingService(AssetProcessingService):
    async def _complete(self, asset_id, output_key, document) -> None:
        raise FileSafetyError("processing_state_conflict", "资产处理状态发生冲突")


class SimulatedHardCrash(BaseException):
    pass


class HardCrashAfterOutputService(AssetProcessingService):
    async def _complete(self, asset_id, output_key, document) -> None:
        raise SimulatedHardCrash


async def create_asset(session_factory, storage: LocalStorageAdapter) -> FileAsset:
    project = Project(user_id=USER_ID, name="安全解析")
    asset = FileAsset(
        user_id=USER_ID,
        project_id=project.id,
        original_filename="notes.txt",
        file_category="text",
        mime_type="text/plain",
        byte_size=5,
        sha256=sha256(b"hello").hexdigest(),
        storage_provider="local",
        storage_key=storage.build_quarantine_key(
            USER_ID, UUID("019f0000-0000-7000-8000-000000000002"), ".txt"
        ),
        processing_status="quarantined",
        idempotency_key="processing-test",
    )
    asset.id = UUID("019f0000-0000-7000-8000-000000000002")
    path = storage.resolve_asset_key(USER_ID, asset.id, asset.storage_key)
    path.parent.mkdir(parents=True)
    path.write_text("hello", encoding="utf-8")
    async with session_factory() as session:
        session.add_all((project, asset))
        await session.commit()
    return asset


def service(
    session_factory,
    storage,
    output_store,
    scanner,
    parser=None,
    limits: ProcessingLimits | None = None,
):
    processing_limits = limits or ProcessingLimits()
    return AssetProcessingService(
        session_factory,
        storage,
        output_store,
        scanner,
        parser or SafeDocumentParser(processing_limits),
        processing_limits,
    )


async def load_asset(session_factory, asset_id):
    async with session_factory() as session:
        return await session.get(FileAsset, asset_id)


async def create_batch_assets(
    session_factory,
    storage: LocalStorageAdapter,
    byte_sizes: list[int],
) -> list[FileAsset]:
    project = Project(user_id=USER_ID, name="批量安全解析")
    assets = []
    for index, byte_size in enumerate(byte_sizes, start=100):
        asset_id = UUID(f"019f0000-0000-7000-8000-{index:012d}")
        asset = FileAsset(
            id=asset_id,
            user_id=USER_ID,
            project_id=project.id,
            original_filename=f"file-{index}.txt",
            file_category="text",
            mime_type="text/plain",
            byte_size=byte_size,
            sha256=sha256(b"x").hexdigest(),
            storage_provider="local",
            storage_key=storage.build_quarantine_key(USER_ID, asset_id, ".txt"),
            processing_status="quarantined",
            idempotency_key=f"processing-batch-{index}",
        )
        path = storage.resolve_asset_key(USER_ID, asset.id, asset.storage_key)
        path.parent.mkdir(parents=True)
        path.write_bytes(b"x")
        assets.append(asset)
    async with session_factory() as session:
        session.add_all((project, *assets))
        await session.commit()
    return assets


async def test_worker_persists_state_parser_metadata_and_output_without_credit_reserve(
    session_factory, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    output_store = ParsedOutputStore(tmp_path / "output", max_output_bytes=1024)
    asset = await create_asset(session_factory, storage)
    scanner = RecordingCleanScanner(session_factory)

    processed = await service(session_factory, storage, output_store, scanner).process(
        asset.id
    )
    stored = await load_asset(session_factory, asset.id)

    assert processed is True
    assert scanner.statuses == ["scanning"]
    assert stored.processing_status == "ready"
    assert stored.parser_name == "safe-text"
    assert stored.parser_version == "1.0.0"
    assert stored.processing_warnings == []
    assert stored.processing_error_code is None
    assert stored.processing_error_message is None
    assert stored.processing_started_at is not None
    assert stored.processed_at is not None
    assert output_store.resolve_asset_key(
        USER_ID, asset.id, stored.parsed_storage_key
    ).is_file()


async def test_asset_response_exposes_only_safe_processing_metadata(
    session_factory, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    asset = await create_asset(session_factory, storage)
    await service(
        session_factory,
        storage,
        ParsedOutputStore(tmp_path / "output", max_output_bytes=1024),
        FailingScanner("virus_detected"),
    ).process(asset.id)
    stored = await load_asset(session_factory, asset.id)

    response = AssetResponse(**asset_summary(stored).__dict__).model_dump()

    assert response["processing_error_code"] == "virus_detected"
    assert response["processing_error_message"] == "文件未通过安全扫描"
    assert response["processing_warnings"] == []
    assert "parsed_storage_key" not in response
    async with session_factory() as session:
        credit_entries = await session.scalar(
            select(func.count()).select_from(CreditLedger)
        )
    assert credit_entries == 0


async def test_infected_asset_is_rejected_without_parsing(
    session_factory, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    asset = await create_asset(session_factory, storage)
    parser = ExplodingParser(AssertionError("parser must not run"))

    processed = await service(
        session_factory,
        storage,
        ParsedOutputStore(tmp_path / "output", max_output_bytes=1024),
        FailingScanner("virus_detected"),
        parser,
    ).process(asset.id)
    stored = await load_asset(session_factory, asset.id)

    assert processed is True
    assert parser.calls == 0
    assert stored.processing_status == "rejected"
    assert stored.processing_error_code == "virus_detected"
    assert stored.processing_error_message == "文件未通过安全扫描"
    assert stored.parsed_storage_key is None


async def test_parser_failure_is_rejected_with_safe_error(
    session_factory, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    asset = await create_asset(session_factory, storage)
    parser = ExplodingParser(FileSafetyError("file_corrupt", "文件损坏"))

    await service(
        session_factory,
        storage,
        ParsedOutputStore(tmp_path / "output", max_output_bytes=1024),
        RecordingCleanScanner(session_factory),
        parser,
    ).process(asset.id)
    stored = await load_asset(session_factory, asset.id)

    assert stored.processing_status == "rejected"
    assert stored.processing_error_code == "file_corrupt"
    assert stored.processing_error_message == "文件损坏"


async def test_parser_timeout_terminates_child_before_it_can_escape(
    session_factory, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    asset = await create_asset(session_factory, storage)
    marker_path = tmp_path / "parser-escaped.txt"
    limits = ProcessingLimits(parser_timeout_seconds=0.05)
    started_at = time.monotonic()

    await service(
        session_factory,
        storage,
        ParsedOutputStore(tmp_path / "output", max_output_bytes=1024),
        RecordingCleanScanner(session_factory),
        SlowEscapingParser(marker_path, delay_seconds=0.4),
        limits,
    ).process(asset.id)
    elapsed = time.monotonic() - started_at
    await asyncio.sleep(0.45)
    stored = await load_asset(session_factory, asset.id)

    assert elapsed < 0.3
    assert marker_path.exists() is False
    assert stored.processing_status == "rejected"
    assert stored.processing_error_code == "parser_timeout"
    assert stored.processing_error_message == "文件解析超时"


async def test_tampered_quarantine_file_is_rejected_before_scanning(
    session_factory, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    asset = await create_asset(session_factory, storage)
    path = storage.resolve_asset_key(USER_ID, asset.id, asset.storage_key)
    path.write_text("changed", encoding="utf-8")
    scanner = RecordingCleanScanner(session_factory)

    await service(
        session_factory,
        storage,
        ParsedOutputStore(tmp_path / "output", max_output_bytes=1024),
        scanner,
    ).process(asset.id)
    stored = await load_asset(session_factory, asset.id)

    assert scanner.calls == 0
    assert stored.processing_status == "rejected"
    assert stored.processing_error_code == "file_integrity_mismatch"


async def test_unexpected_parser_error_does_not_persist_path_or_exception(
    session_factory, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    asset = await create_asset(session_factory, storage)
    secret_path = str(tmp_path / "private" / "source.txt")

    await service(
        session_factory,
        storage,
        ParsedOutputStore(tmp_path / "output", max_output_bytes=1024),
        RecordingCleanScanner(session_factory),
        ExplodingParser(RuntimeError(f"failed at {secret_path}")),
    ).process(asset.id)
    stored = await load_asset(session_factory, asset.id)

    assert stored.processing_status == "rejected"
    assert stored.processing_error_code == "processing_failed"
    assert stored.processing_error_message == "文件处理失败"
    assert secret_path not in stored.processing_error_message


async def test_only_one_concurrent_worker_claims_asset(
    session_factory, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    asset = await create_asset(session_factory, storage)
    scanner = SlowScanner()
    worker = service(
        session_factory,
        storage,
        ParsedOutputStore(tmp_path / "output", max_output_bytes=1024),
        scanner,
    )

    first = asyncio.create_task(worker.process(asset.id))
    await scanner.started.wait()
    second_result = await worker.process(asset.id)
    scanner.release.set()
    first_result = await first

    assert sorted((first_result, second_result)) == [False, True]
    assert scanner.calls == 1


@pytest.mark.parametrize("processing_status", ["scanning", "parsing"])
async def test_polling_reconciles_stale_processing_lease_to_rejected(
    session_factory, tmp_path, processing_status
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    asset = await create_asset(session_factory, storage)
    async with session_factory() as session:
        stored = await session.get(FileAsset, asset.id)
        stored.processing_status = processing_status
        stored.processing_started_at = utc_now() - timedelta(minutes=10)
        await session.commit()
    worker = service(
        session_factory,
        storage,
        ParsedOutputStore(tmp_path / "output", max_output_bytes=1024),
        RecordingCleanScanner(session_factory),
        limits=ProcessingLimits(processing_lease_seconds=60),
    )

    processed = await worker.process_next()
    stored = await load_asset(session_factory, asset.id)

    assert processed is False
    assert stored.processing_status == "rejected"
    assert stored.processing_error_code == "processing_lease_expired"
    assert stored.processing_error_message == "文件处理租约已过期"
    assert stored.processed_at is not None


@pytest.mark.parametrize(
    "byte_sizes",
    [
        [1] * 21,
        [10 * 1024 * 1024] * 19 + [10 * 1024 * 1024 + 1],
    ],
)
async def test_batch_over_limits_is_rejected_before_any_claim_or_scan(
    session_factory, tmp_path, byte_sizes
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    assets = await create_batch_assets(session_factory, storage, byte_sizes)
    scanner = RecordingCleanScanner(session_factory)
    worker = service(
        session_factory,
        storage,
        ParsedOutputStore(tmp_path / "output", max_output_bytes=1024),
        scanner,
    )

    with pytest.raises(FileSafetyError):
        await worker.process_batch([asset.id for asset in assets])

    async with session_factory() as session:
        statuses = list(
            await session.scalars(
                select(FileAsset.processing_status).where(
                    FileAsset.id.in_([asset.id for asset in assets])
                )
            )
        )
    assert set(statuses) == {"quarantined"}
    assert scanner.calls == 0


async def test_batch_exact_20_files_and_200_mebibytes_passes_preflight(
    session_factory, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path / "input")
    assets = await create_batch_assets(
        session_factory, storage, [10 * 1024 * 1024] * 20
    )
    worker = service(
        session_factory,
        storage,
        ParsedOutputStore(tmp_path / "output", max_output_bytes=1024),
        RecordingCleanScanner(session_factory),
    )

    processed_count = await worker.process_batch([asset.id for asset in assets])

    async with session_factory() as session:
        statuses = list(
            await session.scalars(
                select(FileAsset.processing_status).where(
                    FileAsset.id.in_([asset.id for asset in assets])
                )
            )
        )
    assert processed_count == 20
    assert set(statuses) == {"rejected"}


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
    assert reconciled.processing_error_code == "processing_lease_expired"
    assert reconciled.parsed_storage_key == expected_key
    assert output_store.resolve_asset_key(USER_ID, asset.id, expected_key).is_file()
