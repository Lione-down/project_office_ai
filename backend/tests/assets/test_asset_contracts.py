from pathlib import Path

from app.services.asset_contracts import (
    FILE_TYPE_POLICIES,
    asset_summary,
    sanitize_filename,
    validate_file_signature,
)
from app.models.file_assets import FileAsset


def test_signature_probe_reads_only_header(monkeypatch, tmp_path) -> None:
    path = tmp_path / "report.pdf"
    path.write_bytes(b"%PDF-1.7\n" + b"payload" * 100)

    def reject_whole_file_read(_path: Path) -> bytes:
        raise AssertionError("signature probe must not read the whole file")

    monkeypatch.setattr(Path, "read_bytes", reject_whole_file_read)

    validate_file_signature(path, ".pdf", FILE_TYPE_POLICIES[".pdf"])


def test_filename_sanitizer_removes_ascii_and_unicode_control_characters() -> None:
    cleaned = sanitize_filename("../控\x00制\x7f\u200b报告.txt")

    assert cleaned == "控制报告.txt"


def test_asset_summary_exposes_safe_processing_metadata_without_storage_keys() -> None:
    asset = FileAsset(
        processing_status="rejected",
        parser_name="safe-xlsx",
        parser_version="1.0.0",
        processing_warnings=["external_links_ignored"],
        processing_error_code="file_corrupt",
        processing_error_message="文件损坏",
        parsed_storage_key="users/private/parsed/content.json",
    )

    summary = asset_summary(asset)

    assert summary.parser_name == "safe-xlsx"
    assert summary.parser_version == "1.0.0"
    assert summary.processing_warnings == ["external_links_ignored"]
    assert summary.processing_error_code == "file_corrupt"
    assert summary.processing_error_message == "文件损坏"
    assert not hasattr(summary, "parsed_storage_key")
