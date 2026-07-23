from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import shutil
from uuid import UUID


class ExcelOutputStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredExcelOutput:
    storage_key: str
    path: Path
    sha256: str
    byte_size: int


class ExcelOutputStore:
    def __init__(self, root: str | Path, *, max_bytes: int = 200 * 1024 * 1024):
        self._root = Path(root).resolve()
        self._max_bytes = max_bytes

    @staticmethod
    def build_key(user_id: UUID, asset_id: UUID) -> str:
        return f"users/{user_id}/outputs/{asset_id}/analysis.xlsx"

    def resolve_key(self, storage_key: str) -> Path:
        key = PurePosixPath(storage_key)
        parts = key.parts
        try:
            valid = (
                not key.is_absolute()
                and len(parts) == 5
                and parts[0] == "users"
                and UUID(parts[1]).version is not None
                and parts[2] == "outputs"
                and UUID(parts[3]).version is not None
                and parts[4] == "analysis.xlsx"
            )
        except (ValueError, AttributeError):
            valid = False
        if not valid:
            raise ExcelOutputStoreError("output_key_invalid")
        path = self._root.joinpath(*parts).resolve()
        if not path.is_relative_to(self._root):
            raise ExcelOutputStoreError("output_key_invalid")
        return path

    def persist(
        self, user_id: UUID, asset_id: UUID, source: str | Path
    ) -> StoredExcelOutput:
        source_path = Path(source).resolve()
        if not source_path.is_file():
            raise ExcelOutputStoreError("renderer_output_missing")
        storage_key = self.build_key(user_id, asset_id)
        destination = self.resolve_key(storage_key)
        directory = destination.parent
        temporary = directory / "analysis.xlsx.tmp"
        try:
            directory.mkdir(parents=True, exist_ok=False)
            digest = sha256()
            byte_size = 0
            with (
                source_path.open("rb") as source_handle,
                temporary.open("xb") as target_handle,
            ):
                while chunk := source_handle.read(1024 * 1024):
                    byte_size += len(chunk)
                    if byte_size > self._max_bytes:
                        raise ExcelOutputStoreError("renderer_output_too_large")
                    digest.update(chunk)
                    target_handle.write(chunk)
                target_handle.flush()
                os.fsync(target_handle.fileno())
            os.replace(temporary, destination)
        except FileExistsError as exception:
            raise ExcelOutputStoreError("output_already_exists") from exception
        except Exception:
            try:
                shutil.rmtree(directory)
            except FileNotFoundError:
                pass
            raise
        return StoredExcelOutput(
            storage_key=storage_key,
            path=destination,
            sha256=digest.hexdigest(),
            byte_size=byte_size,
        )

    def inspect(self, user_id: UUID, asset_id: UUID) -> StoredExcelOutput | None:
        storage_key = self.build_key(user_id, asset_id)
        path = self.resolve_key(storage_key)
        if not path.is_file():
            return None
        digest = sha256()
        byte_size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                byte_size += len(chunk)
                if byte_size > self._max_bytes:
                    raise ExcelOutputStoreError("renderer_output_too_large")
                digest.update(chunk)
        return StoredExcelOutput(
            storage_key=storage_key,
            path=path,
            sha256=digest.hexdigest(),
            byte_size=byte_size,
        )
