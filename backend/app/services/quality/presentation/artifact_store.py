from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
from uuid import UUID

from pydantic import ValidationError

from app.services.quality.presentation.contracts import PresentationQualityReport
from app.services.quality.presentation.libreoffice import LibreOfficeConversion


MAX_REPORT_BYTES = 1024 * 1024
MAX_PRESENTATION_BYTES = 100 * 1024 * 1024
MAX_PREVIEW_BYTES = 20 * 1024 * 1024


class PresentationQualityStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredQualityArtifact:
    key: str
    path: Path
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class StoredQualityReport:
    report_key: str
    report_path: Path
    report_sha256: str
    report_byte_size: int
    preview_keys: tuple[str, ...]


class PresentationQualityArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def stage_repaired(
        self, user_id: UUID, asset_id: UUID, source: str | Path
    ) -> StoredQualityArtifact:
        quality_dir = self._quality_dir(user_id, asset_id, create=True)
        key = self._key(user_id, asset_id, "quality", "repaired.pptx")
        destination = quality_dir / "repaired.pptx"
        digest, byte_size = self._copy_once(
            Path(source), destination, MAX_PRESENTATION_BYTES
        )
        return StoredQualityArtifact(key, destination, digest, byte_size)

    def resolve_repaired(
        self, user_id: UUID, asset_id: UUID, key_value: str
    ) -> StoredQualityArtifact:
        expected = self._key(user_id, asset_id, "quality", "repaired.pptx")
        if key_value != expected:
            raise PresentationQualityStoreError("quality_artifact_key_invalid")
        path = self._resolve_key(key_value)
        digest, byte_size = self._digest(path, MAX_PRESENTATION_BYTES)
        return StoredQualityArtifact(key_value, path, digest, byte_size)

    def persist_report(
        self,
        user_id: UUID,
        asset_id: UUID,
        report: PresentationQualityReport,
        *,
        conversion: LibreOfficeConversion | None,
    ) -> StoredQualityReport:
        if report.source.asset_id != asset_id:
            raise PresentationQualityStoreError("quality_report_source_invalid")
        quality_dir = self._quality_dir(user_id, asset_id, create=True)
        preview_keys: list[str] = []
        if conversion is None:
            if report.libreoffice.status == "passed" or report.previews:
                raise PresentationQualityStoreError("quality_preview_invalid")
        else:
            self._validate_conversion(report, conversion)
            pdf_key = self._key(user_id, asset_id, "quality", "preview.pdf")
            self._copy_once(
                conversion.pdf.path,
                quality_dir / "preview.pdf",
                MAX_PRESENTATION_BYTES,
                expected_sha256=conversion.pdf.sha256,
                expected_byte_size=conversion.pdf.byte_size,
            )
            preview_keys.append(pdf_key)
            pages_dir = quality_dir / "pages"
            pages_dir.mkdir(exist_ok=True)
            for page in conversion.pages:
                page_name = f"page-{page.page_number:04d}.png"
                self._copy_once(
                    page.path,
                    pages_dir / page_name,
                    MAX_PREVIEW_BYTES,
                    expected_sha256=page.sha256,
                    expected_byte_size=page.byte_size,
                )
                preview_keys.append(
                    self._key(
                        user_id,
                        asset_id,
                        "quality",
                        "pages",
                        page_name,
                    )
                )
        report_bytes = self._report_bytes(report)
        report_path = quality_dir / "report.json"
        report_digest, report_size = self._write_bytes_once(
            report_bytes, report_path, MAX_REPORT_BYTES
        )
        return StoredQualityReport(
            report_key=self._key(user_id, asset_id, "quality", "report.json"),
            report_path=report_path,
            report_sha256=report_digest,
            report_byte_size=report_size,
            preview_keys=tuple(preview_keys),
        )

    def load_report(
        self,
        user_id: UUID,
        asset_id: UUID,
        report_key: str,
        expected_sha256: str,
    ) -> PresentationQualityReport:
        expected_key = self._key(user_id, asset_id, "quality", "report.json")
        if report_key != expected_key:
            raise PresentationQualityStoreError("quality_artifact_key_invalid")
        path = self._resolve_key(report_key)
        try:
            payload = path.read_bytes()
        except OSError as exception:
            raise PresentationQualityStoreError("quality_report_missing") from exception
        if (
            not payload
            or len(payload) > MAX_REPORT_BYTES
            or sha256(payload).hexdigest() != expected_sha256
        ):
            raise PresentationQualityStoreError("quality_report_integrity_failed")
        try:
            report = PresentationQualityReport.model_validate_json(payload)
        except ValidationError as exception:
            raise PresentationQualityStoreError(
                "quality_report_integrity_failed"
            ) from exception
        if report.source.asset_id != asset_id:
            raise PresentationQualityStoreError("quality_report_integrity_failed")
        return report

    def recover_report(
        self, user_id: UUID, asset_id: UUID
    ) -> tuple[PresentationQualityReport, StoredQualityReport] | None:
        report_key = self._key(user_id, asset_id, "quality", "report.json")
        report_path = self._resolve_key(report_key)
        if not report_path.is_file():
            return None
        payload = report_path.read_bytes()
        if not payload or len(payload) > MAX_REPORT_BYTES:
            raise PresentationQualityStoreError("quality_report_integrity_failed")
        try:
            report = PresentationQualityReport.model_validate_json(payload)
        except ValidationError as exception:
            raise PresentationQualityStoreError(
                "quality_report_integrity_failed"
            ) from exception
        if report.source.asset_id != asset_id:
            raise PresentationQualityStoreError("quality_report_integrity_failed")
        preview_keys: list[str] = []
        if report.libreoffice.status == "passed":
            preview_keys.append(self._key(user_id, asset_id, "quality", "preview.pdf"))
            preview_keys.extend(
                self._key(
                    user_id,
                    asset_id,
                    "quality",
                    "pages",
                    f"page-{page.page_number:04d}.png",
                )
                for page in report.previews
            )
        return report, StoredQualityReport(
            report_key=report_key,
            report_path=report_path,
            report_sha256=sha256(payload).hexdigest(),
            report_byte_size=len(payload),
            preview_keys=tuple(preview_keys),
        )

    def verify_report_artifacts(
        self,
        user_id: UUID,
        asset_id: UUID,
        report: PresentationQualityReport,
    ) -> None:
        if report.libreoffice.status != "passed":
            if report.previews:
                raise PresentationQualityStoreError("quality_preview_integrity_failed")
            return
        pdf_path = self._resolve_key(
            self._key(user_id, asset_id, "quality", "preview.pdf")
        )
        try:
            pdf_digest, pdf_size = self._digest(pdf_path, MAX_PRESENTATION_BYTES)
            if (
                pdf_digest != report.libreoffice.pdf_sha256
                or pdf_size != report.libreoffice.pdf_byte_size
            ):
                raise PresentationQualityStoreError("quality_preview_integrity_failed")
            for preview in report.previews:
                page_path = self._resolve_key(
                    self._key(
                        user_id,
                        asset_id,
                        "quality",
                        "pages",
                        f"page-{preview.page_number:04d}.png",
                    )
                )
                digest, byte_size = self._digest(page_path, MAX_PREVIEW_BYTES)
                if digest != preview.sha256 or byte_size != preview.byte_size:
                    raise PresentationQualityStoreError(
                        "quality_preview_integrity_failed"
                    )
        except PresentationQualityStoreError as exception:
            if str(exception) == "quality_preview_integrity_failed":
                raise
            raise PresentationQualityStoreError(
                "quality_preview_integrity_failed"
            ) from exception

    def _quality_dir(self, user_id: UUID, asset_id: UUID, *, create: bool) -> Path:
        asset_dir = (
            self._root / "users" / str(user_id) / "outputs" / str(asset_id)
        ).resolve()
        if not asset_dir.is_relative_to(self._root) or not asset_dir.is_dir():
            raise PresentationQualityStoreError("quality_asset_root_missing")
        quality_dir = asset_dir / "quality"
        if create:
            quality_dir.mkdir(exist_ok=True)
        return quality_dir

    def _resolve_key(self, key_value: str) -> Path:
        key = PurePosixPath(key_value)
        if key.is_absolute():
            raise PresentationQualityStoreError("quality_artifact_key_invalid")
        path = self._root.joinpath(*key.parts).resolve()
        if not path.is_relative_to(self._root):
            raise PresentationQualityStoreError("quality_artifact_key_invalid")
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
        expected_sha256: str | None = None,
        expected_byte_size: int | None = None,
    ) -> tuple[str, int]:
        source_digest, source_size = self._digest(source, maximum)
        if (
            expected_sha256 is not None
            and source_digest != expected_sha256
            or expected_byte_size is not None
            and source_size != expected_byte_size
        ):
            raise PresentationQualityStoreError("quality_artifact_integrity_failed")
        if destination.exists():
            destination_digest, destination_size = self._digest(destination, maximum)
            if (destination_digest, destination_size) != (
                source_digest,
                source_size,
            ):
                raise PresentationQualityStoreError("quality_artifact_conflict")
            return destination_digest, destination_size
        temporary = destination.with_name(f"{destination.name}.tmp")
        try:
            with source.open("rb") as source_handle, temporary.open("xb") as target:
                while chunk := source_handle.read(1024 * 1024):
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, destination)
        except FileExistsError:
            temporary.unlink(missing_ok=True)
            return self._copy_once(
                source,
                destination,
                maximum,
                expected_sha256=expected_sha256,
                expected_byte_size=expected_byte_size,
            )
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return source_digest, source_size

    def _write_bytes_once(
        self, payload: bytes, destination: Path, maximum: int
    ) -> tuple[str, int]:
        if not payload or len(payload) > maximum:
            raise PresentationQualityStoreError("quality_report_too_large")
        expected_digest = sha256(payload).hexdigest()
        if destination.exists():
            existing_digest, existing_size = self._digest(destination, maximum)
            if existing_digest != expected_digest or existing_size != len(payload):
                raise PresentationQualityStoreError("quality_artifact_conflict")
            return existing_digest, existing_size
        temporary = destination.with_name(f"{destination.name}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return expected_digest, len(payload)

    @staticmethod
    def _digest(path: Path, maximum: int) -> tuple[str, int]:
        if not path.is_file():
            raise PresentationQualityStoreError("quality_artifact_missing")
        digest = sha256()
        byte_size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                byte_size += len(chunk)
                if byte_size > maximum:
                    raise PresentationQualityStoreError("quality_artifact_too_large")
                digest.update(chunk)
        return digest.hexdigest(), byte_size

    @staticmethod
    def _report_bytes(report: PresentationQualityReport) -> bytes:
        return json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    @staticmethod
    def _validate_conversion(
        report: PresentationQualityReport, conversion: LibreOfficeConversion
    ) -> None:
        if (
            report.libreoffice.status != "passed"
            or report.libreoffice.pdf_sha256 != conversion.pdf.sha256
            or report.libreoffice.pdf_byte_size != conversion.pdf.byte_size
            or report.libreoffice.page_count != len(conversion.pages)
            or len(report.previews) != len(conversion.pages)
        ):
            raise PresentationQualityStoreError("quality_preview_invalid")
        for reference, page in zip(report.previews, conversion.pages, strict=True):
            if (
                reference.page_number != page.page_number
                or reference.sha256 != page.sha256
                or reference.byte_size != page.byte_size
                or reference.width != page.width
                or reference.height != page.height
            ):
                raise PresentationQualityStoreError("quality_preview_invalid")
