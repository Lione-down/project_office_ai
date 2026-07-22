from dataclasses import dataclass
from pathlib import Path


MEBIBYTE = 1024 * 1024


class FileSafetyError(Exception):
    def __init__(self, error_code: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.error_code = error_code
        self.safe_message = safe_message

    def __reduce__(self):
        return (type(self), (self.error_code, self.safe_message))


@dataclass(frozen=True)
class ProcessingLimits:
    max_file_bytes: int = 50 * MEBIBYTE
    max_image_bytes: int = 20 * MEBIBYTE
    max_image_decoded_bytes: int = 128 * MEBIBYTE
    max_task_files: int = 20
    max_task_bytes: int = 200 * MEBIBYTE
    max_pdf_pages: int = 200
    max_excel_sheets: int = 30
    max_excel_non_empty_cells: int = 300_000
    max_archive_entries: int = 10_000
    max_archive_uncompressed_bytes: int = 250 * MEBIBYTE
    max_archive_compression_ratio: int = 100
    max_office_xml_member_bytes: int = 16 * MEBIBYTE
    max_parser_structural_items: int = 1_500_000
    max_output_bytes: int = 10 * MEBIBYTE
    parser_timeout_seconds: float = 30.0
    processing_lease_seconds: int = 300


@dataclass
class StructuralBudget:
    limit: int
    consumed: int = 0

    def consume(self, count: int = 1) -> None:
        self.consumed += count
        if self.consumed > self.limit:
            raise FileSafetyError(
                "parser_structure_limit_exceeded", "文件结构超过解析安全上限"
            )


@dataclass(frozen=True)
class FileDescriptor:
    path: Path
    extension: str
    mime_type: str
    byte_size: int
    category: str


def validate_processing_batch(
    files: list[FileDescriptor], limits: ProcessingLimits
) -> None:
    if len(files) > limits.max_task_files:
        raise FileSafetyError("task_file_limit_exceeded", "任务文件数量超过允许上限")
    total_bytes = 0
    for file in files:
        if file.byte_size > limits.max_file_bytes:
            raise FileSafetyError("file_too_large", "文件大小超过允许上限")
        if file.category == "image" and file.byte_size > limits.max_image_bytes:
            raise FileSafetyError("image_too_large", "图片大小超过允许上限")
        total_bytes += file.byte_size
    if total_bytes > limits.max_task_bytes:
        raise FileSafetyError("task_size_limit_exceeded", "任务总大小超过允许上限")


def validate_excel_shape(
    sheet_count: int, non_empty_cell_count: int, limits: ProcessingLimits
) -> None:
    if sheet_count > limits.max_excel_sheets:
        raise FileSafetyError(
            "excel_sheet_limit_exceeded", "Excel Sheet 数量超过允许上限"
        )
    if non_empty_cell_count > limits.max_excel_non_empty_cells:
        raise FileSafetyError(
            "excel_cell_limit_exceeded", "Excel 非空单元格数量超过允许上限"
        )
