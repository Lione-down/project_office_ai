import asyncio
from collections.abc import AsyncIterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
import shutil
from uuid import UUID


SAFE_EXTENSION = re.compile(r"^\.[a-z0-9]{1,10}$")
SAFE_OBJECT_NAME = re.compile(r"^original\.[a-z0-9]{1,10}$")


class StorageOperationError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


def has_cleanup_failure(exception: BaseException) -> bool:
    return bool(getattr(exception, "quarantine_cleanup_failed", False))


def record_cleanup_failure(
    original_error: BaseException, cleanup_error: BaseException
) -> None:
    original_error.quarantine_cleanup_failed = True
    original_error.add_note(f"cleanup failed: {type(cleanup_error).__name__}")


@dataclass(frozen=True)
class StoredObject:
    storage_key: str
    byte_size: int
    sha256: str


class LocalStorageAdapter:
    provider = "local"

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def build_quarantine_key(
        self, user_id: UUID, asset_id: UUID, extension: str
    ) -> str:
        normalized_extension = extension.lower()
        if not SAFE_EXTENSION.fullmatch(normalized_extension):
            raise StorageOperationError("file_extension_invalid", "文件扩展名无效")
        return f"users/{user_id}/quarantine/{asset_id}/original{normalized_extension}"

    def resolve_key(self, storage_key: str) -> Path:
        key = PurePosixPath(storage_key)
        parts = key.parts
        try:
            has_asset_prefix = (
                len(parts) >= 5
                and parts[0] == "users"
                and UUID(parts[1]).version is not None
                and UUID(parts[3]).version is not None
            )
            is_quarantine = (
                len(parts) == 5
                and parts[2] == "quarantine"
                and SAFE_OBJECT_NAME.fullmatch(parts[4]) is not None
            )
            is_generated_output = (
                len(parts) == 5
                and parts[2] == "outputs"
                and parts[4] == "presentation.pptx"
            )
            is_quality_repaired_output = (
                len(parts) == 6
                and parts[2] == "outputs"
                and parts[4:] == ("quality", "repaired.pptx")
            )
            is_valid = (
                not key.is_absolute()
                and has_asset_prefix
                and (is_quarantine or is_generated_output or is_quality_repaired_output)
            )
        except (ValueError, AttributeError):
            is_valid = False
        if not is_valid:
            raise StorageOperationError("storage_key_invalid", "存储路径无效")
        resolved = self._root.joinpath(*parts).resolve()
        if not resolved.is_relative_to(self._root):
            raise StorageOperationError("storage_key_invalid", "存储路径无效")
        return resolved

    def resolve_asset_key(
        self, user_id: UUID, asset_id: UUID, storage_key: str
    ) -> Path:
        path = self.resolve_key(storage_key)
        parts = PurePosixPath(storage_key).parts
        if parts[1] != str(user_id) or parts[3] != str(asset_id):
            raise StorageOperationError("storage_key_invalid", "存储路径无效")
        return path

    async def write_quarantine(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
        extension: str,
        chunks: AsyncIterable[bytes],
        max_bytes: int,
    ) -> StoredObject:
        storage_key = self.build_quarantine_key(user_id, asset_id, extension)
        destination = self.resolve_asset_key(user_id, asset_id, storage_key)
        asset_directory = destination.parent
        asset_directory.mkdir(parents=True, exist_ok=False)
        digest = sha256()
        byte_size = 0
        try:
            with destination.open("xb") as file_handle:
                async for chunk in chunks:
                    byte_size += len(chunk)
                    if byte_size > max_bytes:
                        raise StorageOperationError(
                            "file_too_large", "文件大小超过允许上限", 413
                        )
                    digest.update(chunk)
                    file_handle.write(chunk)
        except (Exception, asyncio.CancelledError) as original_error:
            try:
                shutil.rmtree(asset_directory)
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                record_cleanup_failure(original_error, cleanup_error)
            raise
        return StoredObject(storage_key, byte_size, digest.hexdigest())

    def delete_asset(self, user_id: UUID, asset_id: UUID, storage_key: str) -> None:
        asset_path = self.resolve_asset_key(user_id, asset_id, storage_key)
        asset_directory = asset_path.parent
        if asset_directory.name != str(asset_id):
            raise StorageOperationError("storage_key_invalid", "存储路径无效")
        try:
            shutil.rmtree(asset_directory)
        except FileNotFoundError:
            return
        except OSError as exception:
            raise StorageOperationError(
                "asset_delete_failed", "资产文件删除失败", 500
            ) from exception
