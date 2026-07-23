from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import unicodedata
from uuid import UUID

from app.models.file_assets import FileAsset
from app.models.projects import Project


@dataclass(frozen=True)
class FileTypePolicy:
    mime_types: frozenset[str]
    category: str
    signature: bytes | None = None


FILE_TYPE_POLICIES = {
    ".csv": FileTypePolicy(
        frozenset({"text/csv", "application/csv", "application/vnd.ms-excel"}),
        "spreadsheet",
    ),
    ".docx": FileTypePolicy(
        frozenset(
            {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
        ),
        "document",
        b"PK",
    ),
    ".jpeg": FileTypePolicy(frozenset({"image/jpeg"}), "image", b"\xff\xd8\xff"),
    ".jpg": FileTypePolicy(frozenset({"image/jpeg"}), "image", b"\xff\xd8\xff"),
    ".md": FileTypePolicy(frozenset({"text/markdown", "text/plain"}), "text"),
    ".pdf": FileTypePolicy(frozenset({"application/pdf"}), "document", b"%PDF-"),
    ".png": FileTypePolicy(frozenset({"image/png"}), "image", b"\x89PNG\r\n\x1a\n"),
    ".txt": FileTypePolicy(frozenset({"text/plain"}), "text"),
    ".webp": FileTypePolicy(frozenset({"image/webp"}), "image"),
    ".xlsm": FileTypePolicy(
        frozenset({"application/vnd.ms-excel.sheet.macroenabled.12"}),
        "spreadsheet",
        b"PK",
    ),
    ".xlsx": FileTypePolicy(
        frozenset(
            {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        ),
        "spreadsheet",
        b"PK",
    ),
}


class AssetOperationError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class AssetAuditContext:
    ip_address: str | None
    user_agent: str | None
    trace_id: str


@dataclass(frozen=True)
class ProjectSummary:
    project_id: UUID
    name: str
    is_default: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AssetSummary:
    asset_id: UUID
    project_id: UUID
    original_filename: str
    file_category: str
    mime_type: str
    byte_size: int
    sha256: str
    processing_status: str
    created_at: datetime
    updated_at: datetime
    parser_name: str | None = None
    parser_version: str | None = None
    processing_warnings: list[str] = field(default_factory=list)
    processing_error_code: str | None = None
    processing_error_message: str | None = None
    manifest_status: str | None = None
    manifest_schema_version: str | None = None
    evidence_engine_version: str | None = None
    evidence_warning_count: int | None = None
    evidence_blocker_count: int | None = None


@dataclass(frozen=True)
class AssetContent:
    asset_id: UUID
    path: Path
    filename: str
    mime_type: str


def sanitize_filename(filename: str) -> str:
    normalized = unicodedata.normalize("NFKC", filename).replace("\\", "/")
    basename = normalized.rsplit("/", 1)[-1]
    cleaned = "".join(
        character
        for character in basename
        if not unicodedata.category(character).startswith("C")
    )
    cleaned = cleaned.strip().strip(".")
    if not cleaned:
        raise AssetOperationError("filename_invalid", "文件名无效", 422)
    if len(cleaned) > 255:
        suffix = Path(cleaned).suffix[-11:]
        cleaned = f"{cleaned[: 255 - len(suffix)]}{suffix}"
    return cleaned


def validate_file_type(filename: str, content_type: str) -> tuple[str, FileTypePolicy]:
    extension = Path(filename).suffix.lower()
    policy = FILE_TYPE_POLICIES.get(extension)
    if policy is None:
        raise AssetOperationError("file_type_unsupported", "不支持该文件类型", 415)
    normalized_mime = content_type.partition(";")[0].strip().lower()
    if normalized_mime not in policy.mime_types:
        raise AssetOperationError(
            "file_mime_mismatch", "文件扩展名与MIME类型不一致", 415
        )
    return normalized_mime, policy


def validate_file_signature(path: Path, extension: str, policy: FileTypePolicy) -> None:
    with path.open("rb") as file_handle:
        header = file_handle.read(12)
    is_valid = bool(header)
    if policy.signature is not None:
        is_valid = header.startswith(policy.signature)
    if extension == ".webp":
        is_valid = (
            len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
        )
    if not is_valid:
        raise AssetOperationError(
            "file_signature_invalid", "文件内容与声明类型不一致", 415
        )


def project_summary(project: Project) -> ProjectSummary:
    return ProjectSummary(
        project_id=project.id,
        name=project.name,
        is_default=project.is_default,
        is_archived=project.is_archived,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def asset_summary(asset: FileAsset) -> AssetSummary:
    return AssetSummary(
        asset_id=asset.id,
        project_id=asset.project_id,
        original_filename=asset.original_filename,
        file_category=asset.file_category,
        mime_type=asset.mime_type,
        byte_size=asset.byte_size,
        sha256=asset.sha256,
        processing_status=asset.processing_status,
        parser_name=asset.parser_name,
        parser_version=asset.parser_version,
        processing_warnings=list(asset.processing_warnings or []),
        processing_error_code=asset.processing_error_code,
        processing_error_message=asset.processing_error_message,
        manifest_status=asset.manifest_status,
        manifest_schema_version=asset.manifest_schema_version,
        evidence_engine_version=asset.evidence_engine_version,
        evidence_warning_count=asset.evidence_warning_count,
        evidence_blocker_count=asset.evidence_blocker_count,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )
