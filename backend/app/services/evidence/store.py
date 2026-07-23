from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.services.evidence.contracts import (
    EvidenceManifest,
    EvidenceProcessingError,
)


@dataclass(frozen=True)
class StoredManifest:
    storage_key: str
    byte_size: int
    sha256: str


class EvidenceManifestStore:
    def __init__(self, root: str | Path, *, max_output_bytes: int) -> None:
        self._root = Path(root).resolve()
        self._max_output_bytes = max_output_bytes

    @staticmethod
    def build_key(user_id: UUID, asset_id: UUID) -> str:
        return f"users/{user_id}/assets/{asset_id}/extracted/evidence-manifest.json"

    def resolve_asset_key(
        self, user_id: UUID, asset_id: UUID, storage_key: str
    ) -> Path:
        key = PurePosixPath(storage_key)
        parts = key.parts
        try:
            valid = (
                not key.is_absolute()
                and len(parts) == 6
                and parts[0] == "users"
                and parts[2] == "assets"
                and parts[4] == "extracted"
                and parts[5] == "evidence-manifest.json"
                and UUID(parts[1]) == user_id
                and UUID(parts[3]) == asset_id
            )
        except (ValueError, AttributeError):
            valid = False
        if not valid:
            raise EvidenceProcessingError(
                "evidence_manifest_key_invalid", "Evidence Manifest 存储路径无效"
            )
        path = self._root.joinpath(*parts).resolve()
        if not path.is_relative_to(self._root):
            raise EvidenceProcessingError(
                "evidence_manifest_key_invalid", "Evidence Manifest 存储路径无效"
            )
        return path

    def write(
        self, user_id: UUID, asset_id: UUID, manifest: EvidenceManifest
    ) -> StoredManifest:
        payload = json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(payload) > self._max_output_bytes:
            raise EvidenceProcessingError(
                "evidence_manifest_too_large", "Evidence Manifest 超过允许上限"
            )
        key = self.build_key(user_id, asset_id)
        destination = self.resolve_asset_key(user_id, asset_id, key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.parent / f".evidence-{uuid4()}.tmp"
        try:
            with temporary.open("xb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(destination)
        except OSError as exception:
            temporary.unlink(missing_ok=True)
            raise EvidenceProcessingError(
                "evidence_manifest_write_failed", "Evidence Manifest 写入失败"
            ) from exception
        return StoredManifest(
            storage_key=key,
            byte_size=len(payload),
            sha256=sha256(payload).hexdigest(),
        )

    def read(
        self,
        user_id: UUID,
        asset_id: UUID,
        storage_key: str,
        *,
        expected_sha256: str,
    ) -> EvidenceManifest:
        path = self.resolve_asset_key(user_id, asset_id, storage_key)
        try:
            with path.open("rb") as input_file:
                payload = input_file.read(self._max_output_bytes + 1)
        except OSError as exception:
            raise EvidenceProcessingError(
                "evidence_manifest_unavailable", "Evidence Manifest 不可用"
            ) from exception
        if (
            len(payload) > self._max_output_bytes
            or sha256(payload).hexdigest() != expected_sha256
        ):
            raise EvidenceProcessingError(
                "evidence_manifest_integrity_failed",
                "Evidence Manifest 完整性校验失败",
            )
        try:
            manifest = EvidenceManifest.model_validate_json(payload)
        except ValidationError as exception:
            raise EvidenceProcessingError(
                "evidence_manifest_invalid", "Evidence Manifest Schema 无效"
            ) from exception
        if manifest.asset_id != asset_id:
            raise EvidenceProcessingError(
                "evidence_manifest_integrity_failed",
                "Evidence Manifest 资产绑定无效",
            )
        return manifest

    def delete(self, user_id: UUID, asset_id: UUID, storage_key: str) -> None:
        path = self.resolve_asset_key(user_id, asset_id, storage_key)
        try:
            path.unlink()
        except FileNotFoundError:
            return
        except OSError as exception:
            raise EvidenceProcessingError(
                "evidence_manifest_delete_failed", "Evidence Manifest 清理失败"
            ) from exception
        for directory in (path.parent, path.parent.parent, path.parent.parent.parent):
            try:
                directory.rmdir()
            except OSError:
                break
