import json
from pathlib import Path, PurePosixPath
import os
from uuid import UUID, uuid4

from app.services.file_safety.contracts import FileSafetyError
from app.services.file_safety.parsers import ParsedDocument


class ParsedOutputStore:
    def __init__(self, root: str | Path, *, max_output_bytes: int) -> None:
        self._root = Path(root).resolve()
        self._max_output_bytes = max_output_bytes

    def build_key(self, user_id: UUID, asset_id: UUID) -> str:
        return f"users/{user_id}/parsed/{asset_id}/content.json"

    def resolve_asset_key(
        self, user_id: UUID, asset_id: UUID, storage_key: str
    ) -> Path:
        key = PurePosixPath(storage_key)
        parts = key.parts
        is_valid = (
            not key.is_absolute()
            and len(parts) == 5
            and parts[0] == "users"
            and parts[1] == str(user_id)
            and parts[2] == "parsed"
            and parts[3] == str(asset_id)
            and parts[4] == "content.json"
        )
        if not is_valid:
            raise FileSafetyError("parsed_storage_key_invalid", "解析结果存储路径无效")
        path = self._root.joinpath(*parts).resolve()
        if not path.is_relative_to(self._root):
            raise FileSafetyError("parsed_storage_key_invalid", "解析结果存储路径无效")
        return path

    def write(self, user_id: UUID, asset_id: UUID, document: ParsedDocument) -> str:
        payload = json.dumps(
            document.to_dict(), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        if len(payload) > self._max_output_bytes:
            raise FileSafetyError("parsed_output_too_large", "解析结果超过允许上限")
        key = self.build_key(user_id, asset_id)
        destination = self.resolve_asset_key(user_id, asset_id, key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.parent / f".content-{uuid4()}.tmp"
        try:
            with temporary.open("xb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(destination)
        except OSError as exception:
            temporary.unlink(missing_ok=True)
            raise FileSafetyError(
                "parsed_output_write_failed", "解析结果写入失败"
            ) from exception
        return key

    def delete(self, user_id: UUID, asset_id: UUID, storage_key: str) -> None:
        path = self.resolve_asset_key(user_id, asset_id, storage_key)
        try:
            path.unlink()
        except FileNotFoundError:
            return
        except OSError as exception:
            raise FileSafetyError(
                "parsed_output_delete_failed", "解析结果清理失败"
            ) from exception
        try:
            path.parent.rmdir()
        except OSError:
            pass
