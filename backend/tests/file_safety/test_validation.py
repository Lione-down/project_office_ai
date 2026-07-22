from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.services.file_safety.contracts import FileSafetyError, ProcessingLimits
from app.services.file_safety.validation import validate_file_for_processing
from tests.file_safety.conftest import write_office_archive


DOCX_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)
PPTX_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
)
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"


def validate(path: Path, extension: str, mime_type: str) -> None:
    validate_file_for_processing(
        path=path,
        extension=extension,
        mime_type=mime_type,
        limits=ProcessingLimits(
            max_archive_uncompressed_bytes=64 * 1024,
            max_archive_compression_ratio=20,
        ),
    )


def test_docx_content_type_is_accepted(tmp_path) -> None:
    path = write_office_archive(tmp_path / "report.docx", content_type=DOCX_TYPE)

    validate(
        path,
        ".docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


def test_pptx_disguised_as_docx_is_rejected(tmp_path) -> None:
    path = write_office_archive(tmp_path / "report.docx", content_type=PPTX_TYPE)

    with pytest.raises(FileSafetyError) as captured:
        validate(
            path,
            ".docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    assert captured.value.error_code == "file_mime_mismatch"


@pytest.mark.parametrize(
    ("extension", "mime_type"),
    [
        (".xls", "application/vnd.ms-excel"),
        (
            ".pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
    ],
)
def test_unsupported_office_inputs_are_rejected(tmp_path, extension, mime_type) -> None:
    path = tmp_path / f"input{extension}"
    path.write_bytes(b"not-used")

    with pytest.raises(FileSafetyError) as captured:
        validate(path, extension, mime_type)

    assert captured.value.error_code == "file_type_unsupported"


def test_corrupt_office_archive_is_rejected(tmp_path) -> None:
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b"PK\x03\x04broken")

    with pytest.raises(FileSafetyError) as captured:
        validate(
            path,
            ".xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    assert captured.value.error_code == "file_corrupt"


def test_ole_encrypted_office_payload_is_rejected(tmp_path) -> None:
    path = tmp_path / "protected.xlsx"
    path.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + b"encrypted-package")

    with pytest.raises(FileSafetyError) as captured:
        validate(
            path,
            ".xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    assert captured.value.error_code == "file_encrypted"


def test_zip_bomb_ratio_is_rejected(tmp_path) -> None:
    path = tmp_path / "bomb.xlsx"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            f'<Types><Override ContentType="{XLSX_TYPE}"/></Types>',
        )
        archive.writestr("xl/worksheets/sheet1.xml", b"0" * (32 * 1024))

    with pytest.raises(FileSafetyError) as captured:
        validate(
            path,
            ".xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    assert captured.value.error_code == "archive_bomb_detected"


def test_archive_path_traversal_member_is_rejected(tmp_path) -> None:
    path = write_office_archive(
        tmp_path / "unsafe.docx",
        content_type=DOCX_TYPE,
        members={"../payload.xml": b"<root/>"},
    )

    with pytest.raises(FileSafetyError) as captured:
        validate(
            path,
            ".docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    assert captured.value.error_code == "archive_member_invalid"


def test_office_content_types_with_dtd_are_rejected(tmp_path) -> None:
    path = tmp_path / "unsafe.xlsx"
    content_types = f"""<!DOCTYPE Types [
<!ENTITY marker "{XLSX_TYPE}">
]><Types><Override ContentType="&marker;"/></Types>"""
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("xl/workbook.xml", b"<workbook/>")

    with pytest.raises(FileSafetyError) as captured:
        validate(
            path,
            ".xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    assert captured.value.error_code == "unsafe_xml_detected"


def test_text_with_nul_bytes_is_rejected_as_mime_spoof(tmp_path) -> None:
    path = tmp_path / "notes.txt"
    path.write_bytes(b"hello\x00world")

    with pytest.raises(FileSafetyError) as captured:
        validate(path, ".txt", "text/plain")

    assert captured.value.error_code == "file_mime_mismatch"
