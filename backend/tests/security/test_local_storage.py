import asyncio
from hashlib import sha256
from uuid import UUID

import pytest

from app.storage.local import LocalStorageAdapter, StorageOperationError


USER_ID = UUID("019f0000-0000-7000-8000-000000000001")
ASSET_ID = UUID("019f0000-0000-7000-8000-000000000101")
OTHER_ASSET_ID = UUID("019f0000-0000-7000-8000-000000000102")


async def chunks(*values: bytes):
    for value in values:
        yield value


def test_quarantine_key_uses_only_immutable_ids_and_safe_extension(tmp_path) -> None:
    storage = LocalStorageAdapter(tmp_path)

    key = storage.build_quarantine_key(USER_ID, ASSET_ID, ".pdf")

    assert key == f"users/{USER_ID}/quarantine/{ASSET_ID}/original.pdf"
    assert "report" not in key
    with pytest.raises(StorageOperationError, match="文件扩展名无效"):
        storage.build_quarantine_key(USER_ID, ASSET_ID, "/../../escape")


def test_resolve_rejects_path_traversal_and_forged_storage_key(tmp_path) -> None:
    storage = LocalStorageAdapter(tmp_path)

    with pytest.raises(StorageOperationError, match="存储路径无效"):
        storage.resolve_key("users")
    with pytest.raises(StorageOperationError, match="存储路径无效"):
        storage.resolve_key(f"users/{USER_ID}/../../outside.txt")
    with pytest.raises(StorageOperationError, match="存储路径无效"):
        storage.resolve_asset_key(
            USER_ID,
            ASSET_ID,
            f"users/{USER_ID}/quarantine/{OTHER_ASSET_ID}/original.pdf",
        )


def test_resolve_accepts_only_the_fixed_generated_presentation_key(tmp_path) -> None:
    storage = LocalStorageAdapter(tmp_path)
    key = f"users/{USER_ID}/outputs/{ASSET_ID}/presentation.pptx"

    assert storage.resolve_key(key) == tmp_path / key.replace("/", "\\")
    with pytest.raises(StorageOperationError, match="存储路径无效"):
        storage.resolve_key(f"users/{USER_ID}/outputs/{ASSET_ID}/other.pptx")


async def test_stream_to_quarantine_hashes_content_without_buffering_whole_file(
    tmp_path,
) -> None:
    storage = LocalStorageAdapter(tmp_path)

    stored = await storage.write_quarantine(
        user_id=USER_ID,
        asset_id=ASSET_ID,
        extension=".pdf",
        chunks=chunks(b"%PDF", b"-safe-test"),
        max_bytes=100,
    )

    assert stored.byte_size == 14
    assert stored.sha256 == sha256(b"%PDF-safe-test").hexdigest()
    assert storage.resolve_asset_key(
        USER_ID, ASSET_ID, stored.storage_key
    ).read_bytes() == (b"%PDF-safe-test")


async def test_stream_rejects_size_overflow_and_removes_partial_asset(tmp_path) -> None:
    storage = LocalStorageAdapter(tmp_path)

    with pytest.raises(StorageOperationError) as captured:
        await storage.write_quarantine(
            user_id=USER_ID,
            asset_id=ASSET_ID,
            extension=".txt",
            chunks=chunks(b"1234", b"5678"),
            max_bytes=7,
        )

    assert captured.value.error_code == "file_too_large"
    assert not (
        tmp_path / "users" / str(USER_ID) / "quarantine" / str(ASSET_ID)
    ).exists()


async def test_write_quarantine_preserves_original_error_when_cleanup_is_missing(
    monkeypatch, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path)

    async def failing_chunks():
        yield b"partial"
        raise RuntimeError("upload stream failed")

    def missing_directory(_path, **_kwargs):
        raise FileNotFoundError("already removed")

    monkeypatch.setattr("app.storage.local.shutil.rmtree", missing_directory)

    with pytest.raises(RuntimeError, match="upload stream failed"):
        await storage.write_quarantine(
            user_id=USER_ID,
            asset_id=ASSET_ID,
            extension=".txt",
            chunks=failing_chunks(),
            max_bytes=100,
        )


async def test_write_quarantine_reports_cleanup_failure_without_hiding_partial_file(
    monkeypatch, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path)

    async def failing_chunks():
        yield b"partial"
        raise OSError("upload stream failed")

    def fail_cleanup(_path, *, ignore_errors=False):
        if ignore_errors:
            return None
        raise PermissionError("directory is locked")

    monkeypatch.setattr("app.storage.local.shutil.rmtree", fail_cleanup)

    with pytest.raises(OSError, match="upload stream failed") as captured:
        await storage.write_quarantine(
            user_id=USER_ID,
            asset_id=ASSET_ID,
            extension=".txt",
            chunks=failing_chunks(),
            max_bytes=100,
        )

    assert any(
        "cleanup failed: PermissionError" in note for note in captured.value.__notes__
    )
    assert (
        storage.resolve_asset_key(
            USER_ID,
            ASSET_ID,
            f"users/{USER_ID}/quarantine/{ASSET_ID}/original.txt",
        ).read_bytes()
        == b"partial"
    )


async def test_write_quarantine_cleans_partial_file_when_stream_is_cancelled(
    tmp_path,
) -> None:
    storage = LocalStorageAdapter(tmp_path)

    async def cancelled_chunks():
        yield b"partial-cancelled-content"
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await storage.write_quarantine(
            user_id=USER_ID,
            asset_id=ASSET_ID,
            extension=".txt",
            chunks=cancelled_chunks(),
            max_bytes=100,
        )

    assert not (
        tmp_path / "users" / str(USER_ID) / "quarantine" / str(ASSET_ID)
    ).exists()


async def test_write_quarantine_reports_cleanup_failure_during_cancellation(
    monkeypatch, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path)

    async def cancelled_chunks():
        yield b"partial-cancelled-content"
        raise asyncio.CancelledError()

    def fail_cleanup(_path):
        raise PermissionError("directory is locked")

    monkeypatch.setattr("app.storage.local.shutil.rmtree", fail_cleanup)

    with pytest.raises(asyncio.CancelledError) as captured:
        await storage.write_quarantine(
            user_id=USER_ID,
            asset_id=ASSET_ID,
            extension=".txt",
            chunks=cancelled_chunks(),
            max_bytes=100,
        )

    assert any(
        "cleanup failed: PermissionError" in note for note in captured.value.__notes__
    )
    assert (tmp_path / "users" / str(USER_ID) / "quarantine" / str(ASSET_ID)).exists()


async def test_delete_asset_removes_only_validated_asset_directory(tmp_path) -> None:
    storage = LocalStorageAdapter(tmp_path)
    first = await storage.write_quarantine(
        user_id=USER_ID,
        asset_id=ASSET_ID,
        extension=".txt",
        chunks=chunks(b"first"),
        max_bytes=100,
    )
    second = await storage.write_quarantine(
        user_id=USER_ID,
        asset_id=OTHER_ASSET_ID,
        extension=".txt",
        chunks=chunks(b"second"),
        max_bytes=100,
    )

    storage.delete_asset(USER_ID, ASSET_ID, first.storage_key)

    assert not storage.resolve_key(first.storage_key).exists()
    assert storage.resolve_asset_key(
        USER_ID, OTHER_ASSET_ID, second.storage_key
    ).exists()


async def test_delete_asset_reports_physical_delete_failure(
    monkeypatch, tmp_path
) -> None:
    storage = LocalStorageAdapter(tmp_path)
    stored = await storage.write_quarantine(
        user_id=USER_ID,
        asset_id=ASSET_ID,
        extension=".txt",
        chunks=chunks(b"sensitive"),
        max_bytes=100,
    )

    def deny_delete(_path):
        raise PermissionError("file is locked")

    monkeypatch.setattr("app.storage.local.shutil.rmtree", deny_delete)

    with pytest.raises(StorageOperationError) as captured:
        storage.delete_asset(USER_ID, ASSET_ID, stored.storage_key)

    assert captured.value.error_code == "asset_delete_failed"
    assert captured.value.status_code == 500
    assert storage.resolve_asset_key(USER_ID, ASSET_ID, stored.storage_key).exists()
