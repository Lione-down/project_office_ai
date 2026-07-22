from pathlib import Path

from app.services.asset_contracts import (
    FILE_TYPE_POLICIES,
    sanitize_filename,
    validate_file_signature,
)


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
