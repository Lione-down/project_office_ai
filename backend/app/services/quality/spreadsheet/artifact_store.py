from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil
from uuid import UUID
from uuid import uuid4

from pydantic import ValidationError

from app.services.quality.spreadsheet.contracts import SpreadsheetQualityReport


MAX_REPORT_BYTES = 1024 * 1024
MAX_VALIDATION_REPORT_BYTES = 10 * 1024 * 1024
MAX_WORKBOOK_BYTES = 200 * 1024 * 1024


class SpreadsheetQualityStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredSpreadsheetQualityArtifacts:
    report_key: str
    report_sha256: str
    report_byte_size: int
    validation_key: str | None
    validation_sha256: str | None
    validation_byte_size: int | None
    validation_report_key: str | None
    validation_report_sha256: str | None
    validation_report_byte_size: int | None
    validated_key: str | None
    validated_sha256: str | None
    validated_byte_size: int | None


class SpreadsheetQualityArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def source_path(self, user_id: UUID, asset_id: UUID) -> Path:
        path = self._asset_dir(user_id, asset_id) / "analysis.xlsx"
        if not path.is_file():
            raise SpreadsheetQualityStoreError("workbook_file_missing")
        return path

    def persist(
        self,
        user_id: UUID,
        asset_id: UUID,
        report: SpreadsheetQualityReport,
        *,
        validation_copy: str | Path | None,
        validation_report_path: str | Path | None,
    ) -> StoredSpreadsheetQualityArtifacts:
        if report.source.asset_id != asset_id:
            raise SpreadsheetQualityStoreError("quality_report_source_invalid")
        quality_dir = self._asset_dir(user_id, asset_id) / "quality"
        quality_dir.mkdir(exist_ok=True)
        validation_key = validation_sha256 = None
        validation_byte_size = None
        validation_report_key = validation_report_sha256 = None
        validation_report_byte_size = None
        validated_key = validated_sha256 = None
        validated_byte_size = None
        if report.validation.status == "passed":
            if validation_copy is None:
                raise SpreadsheetQualityStoreError("quality_validated_copy_missing")
            filename = (
                "validated.xlsx" if report.download_allowed else "validation-copy.xlsx"
            )
            destination = quality_dir / filename
            validation_sha256, validation_byte_size = self._copy_once(
                Path(validation_copy),
                destination,
                MAX_WORKBOOK_BYTES,
                expected_sha256=report.validation.sha256,
                expected_byte_size=report.validation.byte_size,
            )
            validation_key = self._key(user_id, asset_id, "quality", filename)
            if report.download_allowed:
                validated_key = validation_key
                validated_sha256 = validation_sha256
                validated_byte_size = validation_byte_size
            if validation_report_path is None:
                raise SpreadsheetQualityStoreError("quality_validation_report_missing")
            validation_report_sha256, validation_report_byte_size = self._copy_once(
                Path(validation_report_path),
                quality_dir / "libreoffice-report.json",
                MAX_VALIDATION_REPORT_BYTES,
                expected_sha256=report.validation.report_sha256,
                expected_byte_size=None,
            )
            validation_report_key = self._key(
                user_id,
                asset_id,
                "quality",
                "libreoffice-report.json",
            )
        elif validation_copy is not None or validation_report_path is not None:
            raise SpreadsheetQualityStoreError("quality_validation_state_invalid")
        report_bytes = json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        report_sha256, report_size = self._write_once(
            quality_dir / "report.json",
            report_bytes,
            MAX_REPORT_BYTES,
        )
        return StoredSpreadsheetQualityArtifacts(
            report_key=self._key(user_id, asset_id, "quality", "report.json"),
            report_sha256=report_sha256,
            report_byte_size=report_size,
            validation_key=validation_key,
            validation_sha256=validation_sha256,
            validation_byte_size=validation_byte_size,
            validation_report_key=validation_report_key,
            validation_report_sha256=validation_report_sha256,
            validation_report_byte_size=validation_report_byte_size,
            validated_key=validated_key,
            validated_sha256=validated_sha256,
            validated_byte_size=validated_byte_size,
        )

    def load(
        self,
        user_id: UUID,
        asset_id: UUID,
        report_key: str,
        report_sha256: str,
    ) -> tuple[SpreadsheetQualityReport, StoredSpreadsheetQualityArtifacts]:
        expected_key = self._key(user_id, asset_id, "quality", "report.json")
        if report_key != expected_key:
            raise SpreadsheetQualityStoreError("quality_artifact_key_invalid")
        report_path = self._resolve(report_key)
        if report_path.stat().st_size > MAX_REPORT_BYTES:
            raise SpreadsheetQualityStoreError("quality_report_integrity_failed")
        payload = report_path.read_bytes()
        if (
            not payload
            or len(payload) > MAX_REPORT_BYTES
            or sha256(payload).hexdigest() != report_sha256
        ):
            raise SpreadsheetQualityStoreError("quality_report_integrity_failed")
        try:
            report = SpreadsheetQualityReport.model_validate_json(payload)
        except ValidationError as exception:
            raise SpreadsheetQualityStoreError(
                "quality_report_integrity_failed"
            ) from exception
        if report.source.asset_id != asset_id:
            raise SpreadsheetQualityStoreError("quality_report_integrity_failed")
        validation_key = validation_sha256 = None
        validation_byte_size = None
        validation_report_key = validation_report_sha256 = None
        validation_report_byte_size = None
        validated_key = validated_sha256 = None
        validated_byte_size = None
        if report.validation.status == "passed":
            filename = (
                "validated.xlsx" if report.download_allowed else "validation-copy.xlsx"
            )
            validation_key = self._key(user_id, asset_id, "quality", filename)
            validation_sha256, validation_byte_size = self._digest(
                self._resolve(validation_key), MAX_WORKBOOK_BYTES
            )
            if (
                validation_sha256 != report.validation.sha256
                or validation_byte_size != report.validation.byte_size
            ):
                raise SpreadsheetQualityStoreError("quality_validated_integrity_failed")
            if report.download_allowed:
                validated_key = validation_key
                validated_sha256 = validation_sha256
                validated_byte_size = validation_byte_size
            validation_report_key = self._key(
                user_id,
                asset_id,
                "quality",
                "libreoffice-report.json",
            )
            validation_report_sha256, validation_report_byte_size = self._digest(
                self._resolve(validation_report_key), MAX_VALIDATION_REPORT_BYTES
            )
            if validation_report_sha256 != report.validation.report_sha256:
                raise SpreadsheetQualityStoreError(
                    "quality_validation_report_integrity_failed"
                )
        return report, StoredSpreadsheetQualityArtifacts(
            report_key=report_key,
            report_sha256=report_sha256,
            report_byte_size=len(payload),
            validation_key=validation_key,
            validation_sha256=validation_sha256,
            validation_byte_size=validation_byte_size,
            validation_report_key=validation_report_key,
            validation_report_sha256=validation_report_sha256,
            validation_report_byte_size=validation_report_byte_size,
            validated_key=validated_key,
            validated_sha256=validated_sha256,
            validated_byte_size=validated_byte_size,
        )

    def _asset_dir(self, user_id: UUID, asset_id: UUID) -> Path:
        path = (
            self._root / "users" / str(user_id) / "outputs" / str(asset_id)
        ).resolve()
        if not path.is_relative_to(self._root) or not path.is_dir():
            raise SpreadsheetQualityStoreError("quality_asset_root_missing")
        return path

    def _resolve(self, key_value: str) -> Path:
        key = PurePosixPath(key_value)
        path = self._root.joinpath(*key.parts).resolve()
        if key.is_absolute() or not path.is_relative_to(self._root):
            raise SpreadsheetQualityStoreError("quality_artifact_key_invalid")
        return path

    @staticmethod
    def _key(user_id: UUID, asset_id: UUID, *suffix: str) -> str:
        return PurePosixPath(
            "users", str(user_id), "outputs", str(asset_id), *suffix
        ).as_posix()

    def _copy_once(
        self,
        source: Path,
        destination: Path,
        maximum: int,
        *,
        expected_sha256: str | None,
        expected_byte_size: int | None,
    ) -> tuple[str, int]:
        source_sha256, source_size = self._digest(source, maximum)
        if (
            expected_sha256 is not None
            and source_sha256 != expected_sha256
            or expected_byte_size is not None
            and source_size != expected_byte_size
        ):
            raise SpreadsheetQualityStoreError("quality_artifact_integrity_failed")
        if destination.exists():
            current = self._digest(destination, maximum)
            if current != (source_sha256, source_size):
                raise SpreadsheetQualityStoreError("quality_artifact_state_conflict")
            return current
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        try:
            with source.open("rb") as input_handle, temporary.open("xb") as output:
                shutil.copyfileobj(input_handle, output, 1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            os.link(temporary, destination)
        except FileExistsError:
            current = self._digest(destination, maximum)
            if current != (source_sha256, source_size):
                raise SpreadsheetQualityStoreError("quality_artifact_state_conflict")
        finally:
            temporary.unlink(missing_ok=True)
        return source_sha256, source_size

    def _write_once(
        self, destination: Path, payload: bytes, maximum: int
    ) -> tuple[str, int]:
        if not payload or len(payload) > maximum:
            raise SpreadsheetQualityStoreError("quality_report_too_large")
        expected = (sha256(payload).hexdigest(), len(payload))
        if destination.exists():
            if self._digest(destination, maximum) != expected:
                raise SpreadsheetQualityStoreError("quality_report_state_conflict")
            return expected
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if self._digest(destination, maximum) != expected:
                    raise SpreadsheetQualityStoreError("quality_report_state_conflict")
        finally:
            temporary.unlink(missing_ok=True)
        return expected

    @staticmethod
    def _digest(path: Path, maximum: int) -> tuple[str, int]:
        if not path.is_file():
            raise SpreadsheetQualityStoreError("quality_artifact_missing")
        digest = sha256()
        size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                size += len(chunk)
                if size > maximum:
                    raise SpreadsheetQualityStoreError("quality_artifact_too_large")
                digest.update(chunk)
        return digest.hexdigest(), size
