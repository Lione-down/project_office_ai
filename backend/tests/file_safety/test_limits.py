from pathlib import Path

import pytest

from app.services.file_safety.contracts import (
    FileDescriptor,
    FileSafetyError,
    ProcessingLimits,
    validate_excel_shape,
    validate_processing_batch,
)


MEBIBYTE = 1024 * 1024


def descriptor(name: str, size: int, category: str = "document") -> FileDescriptor:
    return FileDescriptor(
        path=Path(name),
        extension=Path(name).suffix,
        mime_type="application/octet-stream",
        byte_size=size,
        category=category,
    )


def test_exact_file_and_image_limits_are_accepted() -> None:
    limits = ProcessingLimits()

    validate_processing_batch(
        [
            descriptor("report.pdf", 50 * MEBIBYTE),
            descriptor("chart.png", 20 * MEBIBYTE, "image"),
        ],
        limits,
    )


@pytest.mark.parametrize(
    ("files", "error_code"),
    [
        ([descriptor("report.pdf", 50 * MEBIBYTE + 1)], "file_too_large"),
        ([descriptor("chart.png", 20 * MEBIBYTE + 1, "image")], "image_too_large"),
        (
            [descriptor(f"file-{index}.txt", 1) for index in range(21)],
            "task_file_limit_exceeded",
        ),
        (
            [descriptor(f"file-{index}.pdf", 10 * MEBIBYTE) for index in range(20)]
            + [descriptor("overflow.txt", 1)],
            "task_file_limit_exceeded",
        ),
        (
            [descriptor(f"file-{index}.pdf", 10 * MEBIBYTE) for index in range(20)]
            + [],
            None,
        ),
    ],
)
def test_processing_batch_limits(files, error_code) -> None:
    if error_code is None:
        validate_processing_batch(files, ProcessingLimits())
        return

    with pytest.raises(FileSafetyError) as captured:
        validate_processing_batch(files, ProcessingLimits())

    assert captured.value.error_code == error_code


def test_task_total_above_200_mebibytes_is_rejected() -> None:
    files = [descriptor(f"file-{index}.pdf", 10 * MEBIBYTE) for index in range(20)]
    files[-1] = descriptor("overflow.pdf", 10 * MEBIBYTE + 1)

    with pytest.raises(FileSafetyError) as captured:
        validate_processing_batch(files, ProcessingLimits())

    assert captured.value.error_code == "task_size_limit_exceeded"


def test_exact_pdf_excel_and_output_contract_limits_are_locked() -> None:
    limits = ProcessingLimits()

    assert limits.max_pdf_pages == 200
    assert limits.max_excel_sheets == 100
    assert limits.max_excel_non_empty_cells == 300_000
    assert limits.max_output_bytes > 0


@pytest.mark.parametrize(
    ("sheet_count", "cell_count", "error_code"),
    [
        (100, 300_000, None),
        (101, 300_000, "excel_sheet_limit_exceeded"),
        (100, 300_001, "excel_cell_limit_exceeded"),
    ],
)
def test_exact_excel_shape_boundaries(sheet_count, cell_count, error_code) -> None:
    if error_code is None:
        validate_excel_shape(sheet_count, cell_count, ProcessingLimits())
        return

    with pytest.raises(FileSafetyError) as captured:
        validate_excel_shape(sheet_count, cell_count, ProcessingLimits())

    assert captured.value.error_code == error_code
