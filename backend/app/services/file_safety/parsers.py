import csv
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree
from xml.parsers import expat
from zipfile import BadZipFile, ZipFile

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.services.file_safety.contracts import (
    FileDescriptor,
    FileSafetyError,
    ProcessingLimits,
    StructuralBudget,
    validate_excel_shape,
)
from app.services.file_safety.pdf_geometry import pdf_text_bbox
from app.services.file_safety.validation import validate_file_for_processing


PARSER_VERSION = "1.0.0"
IMAGE_EXTENSIONS = frozenset({".jpeg", ".jpg", ".png", ".webp"})
TEXT_EXTENSIONS = frozenset({".md", ".txt"})
OFFICE_RELATIONSHIP_ID = (
    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
)


@dataclass(frozen=True)
class ParsedDocument:
    schema_version: str
    parser_name: str
    parser_version: str
    kind: str
    content: dict[str, Any]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["warnings"] = list(self.warnings)
        return value


class SafeDocumentParser:
    def __init__(self, limits: ProcessingLimits) -> None:
        self._limits = limits

    def parse(self, descriptor: FileDescriptor) -> ParsedDocument:
        validate_file_for_processing(
            path=descriptor.path,
            extension=descriptor.extension,
            mime_type=descriptor.mime_type,
            limits=self._limits,
        )
        structure_budget = StructuralBudget(self._limits.max_parser_structural_items)
        extension = descriptor.extension.lower()
        if extension in IMAGE_EXTENSIONS:
            return self._result(
                parser_name="safe-image-gate",
                kind="pending_ocr",
                content={"status": "pending_ocr", "trust": "untrusted"},
            )
        if extension in TEXT_EXTENSIONS:
            return self._parse_text(descriptor.path)
        if extension == ".csv":
            return self._parse_csv(descriptor.path, structure_budget)
        if extension == ".docx":
            return self._parse_docx(descriptor.path, structure_budget)
        if extension in {".xlsx", ".xlsm"}:
            return self._parse_workbook(descriptor.path, extension, structure_budget)
        if extension == ".pdf":
            return self._parse_pdf(descriptor.path)
        raise FileSafetyError("file_type_unsupported", "不支持该文件类型")

    def _parse_text(self, path: Path) -> ParsedDocument:
        try:
            if path.stat().st_size > self._limits.max_output_bytes:
                raise FileSafetyError("parsed_output_too_large", "解析结果超过允许上限")
            text = path.read_text(encoding="utf-8-sig")
            _ensure_content_budget(len(text.encode("utf-8")), self._limits)
        except FileSafetyError:
            raise
        except (OSError, UnicodeDecodeError) as exception:
            raise FileSafetyError("file_parse_failed", "文本解析失败") from exception
        return self._result(
            parser_name="safe-text",
            kind="text",
            content={"text": text, "trust": "untrusted"},
        )

    def _parse_csv(
        self, path: Path, structure_budget: StructuralBudget
    ) -> ParsedDocument:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as file_handle:
                rows = []
                content_bytes = 0
                for row in csv.reader(
                    _budgeted_csv_lines(file_handle, structure_budget)
                ):
                    values = list(row)
                    content_bytes += sum(len(value.encode("utf-8")) for value in values)
                    _ensure_content_budget(content_bytes, self._limits)
                    rows.append(values)
        except FileSafetyError:
            raise
        except (OSError, UnicodeDecodeError, csv.Error) as exception:
            raise FileSafetyError("file_parse_failed", "CSV 解析失败") from exception
        return self._result(
            parser_name="safe-csv",
            kind="table",
            content={"rows": rows, "trust": "untrusted"},
        )

    def _parse_docx(
        self, path: Path, structure_budget: StructuralBudget
    ) -> ParsedDocument:
        try:
            with ZipFile(path) as archive:
                warnings = _archive_warnings(archive, self._limits, structure_budget)
                root = _read_office_xml(
                    archive, "word/document.xml", self._limits, structure_budget
                )
        except FileSafetyError:
            raise
        except (BadZipFile, KeyError, OSError) as exception:
            raise FileSafetyError("file_parse_failed", "DOCX 解析失败") from exception
        paragraphs = []
        paragraph_items = []
        content_bytes = 0
        for paragraph_number, paragraph in enumerate(
            _elements_named(root, "p"), start=1
        ):
            text = "".join(
                node.text or ""
                for node in paragraph.iter()
                if _local_name(node.tag) == "t"
            )
            if text:
                content_bytes += len(text.encode("utf-8"))
                _ensure_content_budget(content_bytes, self._limits)
                paragraphs.append(text)
                paragraph_items.append({"paragraph": paragraph_number, "text": text})
        return self._result(
            parser_name="safe-docx",
            kind="document",
            content={
                "paragraphs": paragraphs,
                "paragraph_items": paragraph_items,
                "trust": "untrusted",
            },
            warnings=warnings,
        )

    def _parse_workbook(
        self,
        path: Path,
        extension: str,
        structure_budget: StructuralBudget,
    ) -> ParsedDocument:
        try:
            with ZipFile(path) as archive:
                warnings = set(
                    _archive_warnings(archive, self._limits, structure_budget)
                )
                names = set(archive.namelist())
                if extension == ".xlsm" and "xl/vbaProject.bin" in names:
                    warnings.add("macros_not_executed")
                workbook = _read_office_xml(
                    archive, "xl/workbook.xml", self._limits, structure_budget
                )
                relationships = _workbook_relationships(
                    archive, self._limits, structure_budget
                )
                shared_strings = _shared_strings(
                    archive, self._limits, structure_budget
                )
                sheet_elements = list(_elements_named(workbook, "sheet"))
                validate_excel_shape(len(sheet_elements), 0, self._limits)
                sheets = []
                non_empty_cells = 0
                content_bytes = 0
                for sheet in sheet_elements:
                    relationship_id = sheet.attrib.get(OFFICE_RELATIONSHIP_ID)
                    if relationship_id is None:
                        relationship_id = sheet.attrib.get("r:id")
                    target = relationships.get(relationship_id or "")
                    if target is None:
                        raise FileSafetyError("file_corrupt", "Excel 文件损坏")
                    worksheet_path = _worksheet_path(target)
                    worksheet = _read_office_xml(
                        archive, worksheet_path, self._limits, structure_budget
                    )
                    rows, cells, count, has_formula, extracted_bytes = _worksheet_rows(
                        worksheet,
                        shared_strings,
                        self._limits.max_output_bytes - content_bytes,
                    )
                    content_bytes += extracted_bytes
                    non_empty_cells += count
                    validate_excel_shape(
                        len(sheet_elements), non_empty_cells, self._limits
                    )
                    if has_formula:
                        warnings.add("formulas_not_executed")
                    sheets.append(
                        {
                            "name": sheet.attrib.get("name", ""),
                            "rows": rows,
                            "cells": cells,
                        }
                    )
        except FileSafetyError:
            raise
        except (BadZipFile, KeyError, OSError, ValueError) as exception:
            raise FileSafetyError("file_parse_failed", "Excel 解析失败") from exception
        return self._result(
            parser_name="safe-xlsm" if extension == ".xlsm" else "safe-xlsx",
            kind="workbook",
            content={
                "sheets": sheets,
                "non_empty_cells": non_empty_cells,
                "trust": "untrusted",
            },
            warnings=tuple(sorted(warnings)),
        )

    def _parse_pdf(self, path: Path) -> ParsedDocument:
        try:
            reader = PdfReader(path, strict=True)
            if reader.is_encrypted:
                raise FileSafetyError("file_encrypted", "文件已加密或受密码保护")
            if len(reader.pages) > self._limits.max_pdf_pages:
                raise FileSafetyError("pdf_page_limit_exceeded", "PDF 页数超过允许上限")
            pages = []
            page_blocks = []
            content_bytes = 0
            for page_number, page in enumerate(reader.pages, start=1):
                blocks = []

                def capture_text(text, current_matrix, text_matrix, _font, font_size):
                    normalized = text.strip()
                    if not normalized:
                        return
                    blocks.append(
                        {
                            "page": page_number,
                            "text": normalized,
                            "bbox": list(
                                pdf_text_bbox(
                                    normalized,
                                    current_matrix,
                                    text_matrix,
                                    font_size,
                                )
                            ),
                        }
                    )

                text = page.extract_text(visitor_text=capture_text) or ""
                content_bytes += len(text.encode("utf-8"))
                _ensure_content_budget(content_bytes, self._limits)
                pages.append(text)
                page_blocks.extend(blocks)
        except FileSafetyError:
            raise
        except (PdfReadError, OSError, ValueError) as exception:
            raise FileSafetyError("file_parse_failed", "PDF 解析失败") from exception
        return self._result(
            parser_name="safe-pypdf",
            kind="document",
            content={
                "pages": pages,
                "page_blocks": page_blocks,
                "trust": "untrusted",
            },
        )

    @staticmethod
    def _result(
        *,
        parser_name: str,
        kind: str,
        content: dict[str, Any],
        warnings: tuple[str, ...] = (),
    ) -> ParsedDocument:
        return ParsedDocument(
            schema_version="parsed-content.v1",
            parser_name=parser_name,
            parser_version=PARSER_VERSION,
            kind=kind,
            content=content,
            warnings=tuple(sorted(warnings)),
        )


def _budgeted_csv_lines(file_handle, structure_budget: StructuralBudget):
    for line in file_handle:
        structure_budget.consume(line.count(",") + 1)
        yield line


def _safe_xml(
    payload: bytes, structure_budget: StructuralBudget
) -> ElementTree.Element:
    upper_payload = payload.upper()
    if b"<!DOCTYPE" in upper_payload or b"<!ENTITY" in upper_payload:
        raise FileSafetyError("unsafe_xml_detected", "文档包含不安全 XML")
    structure_parser = expat.ParserCreate()
    structure_parser.StartElementHandler = lambda _name, _attributes: (
        structure_budget.consume()
    )
    try:
        structure_parser.Parse(payload, True)
    except expat.ExpatError as exception:
        raise FileSafetyError("file_corrupt", "文档 XML 损坏") from exception
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exception:
        raise FileSafetyError("file_corrupt", "文档 XML 损坏") from exception
    return root


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _elements_named(root: ElementTree.Element, name: str):
    return (element for element in root.iter() if _local_name(element.tag) == name)


def _archive_warnings(
    archive: ZipFile,
    limits: ProcessingLimits,
    structure_budget: StructuralBudget,
) -> tuple[str, ...]:
    warnings = set()
    names = archive.namelist()
    if any("/embeddings/" in f"/{name.lower()}" for name in names):
        warnings.add("embedded_objects_ignored")
    if any("/externallinks/" in f"/{name.lower()}" for name in names):
        warnings.add("external_links_ignored")
    for name in names:
        if not name.lower().endswith(".rels"):
            continue
        root = _read_office_xml(archive, name, limits, structure_budget)
        if any(
            element.attrib.get("TargetMode", "").lower() == "external"
            for element in root.iter()
        ):
            warnings.add("external_links_ignored")
    return tuple(sorted(warnings))


def _workbook_relationships(
    archive: ZipFile,
    limits: ProcessingLimits,
    structure_budget: StructuralBudget,
) -> dict[str, str]:
    root = _read_office_xml(
        archive, "xl/_rels/workbook.xml.rels", limits, structure_budget
    )
    return {
        element.attrib["Id"]: element.attrib["Target"]
        for element in root.iter()
        if "Id" in element.attrib and "Target" in element.attrib
    }


def _worksheet_path(target: str) -> str:
    normalized = target.replace("\\", "/").lstrip("/")
    if normalized.startswith("xl/"):
        path = PurePosixPath(normalized)
    else:
        path = PurePosixPath("xl") / normalized
    if ".." in path.parts:
        raise FileSafetyError("archive_member_invalid", "压缩包包含非法路径")
    return path.as_posix()


def _shared_strings(
    archive: ZipFile,
    limits: ProcessingLimits,
    structure_budget: StructuralBudget,
) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = _read_office_xml(archive, "xl/sharedStrings.xml", limits, structure_budget)
    strings = []
    content_bytes = 0
    for item in _elements_named(root, "si"):
        value = "".join(
            node.text or "" for node in item.iter() if _local_name(node.tag) == "t"
        )
        content_bytes += len(value.encode("utf-8"))
        _ensure_content_budget(content_bytes, limits)
        strings.append(value)
    return strings


def _read_office_xml(
    archive: ZipFile,
    member_name: str,
    limits: ProcessingLimits,
    structure_budget: StructuralBudget,
) -> ElementTree.Element:
    member = archive.getinfo(member_name)
    if member.file_size > limits.max_office_xml_member_bytes:
        raise FileSafetyError(
            "office_xml_member_too_large", "Office XML 部件超过安全上限"
        )
    with archive.open(member) as member_handle:
        payload = member_handle.read(limits.max_office_xml_member_bytes + 1)
    if len(payload) > limits.max_office_xml_member_bytes:
        raise FileSafetyError(
            "office_xml_member_too_large", "Office XML 部件超过安全上限"
        )
    return _safe_xml(payload, structure_budget)


def _worksheet_rows(
    worksheet: ElementTree.Element,
    shared_strings: list[str],
    remaining_output_bytes: int,
) -> tuple[list[list[str]], list[dict[str, str]], int, bool, int]:
    rows = []
    cells = []
    non_empty_cells = 0
    has_formula = False
    extracted_bytes = 0
    for row in _elements_named(worksheet, "row"):
        values = []
        for cell in (element for element in row if _local_name(element.tag) == "c"):
            coordinate = cell.attrib.get("r")
            if not coordinate:
                raise FileSafetyError("file_corrupt", "Excel 文件损坏")
            formula = next(_elements_named(cell, "f"), None)
            has_formula = has_formula or formula is not None
            cell_type = cell.attrib.get("t")
            if cell_type == "inlineStr":
                value = "".join(
                    node.text or ""
                    for node in cell.iter()
                    if _local_name(node.tag) == "t"
                )
            else:
                value_node = next(_elements_named(cell, "v"), None)
                value = value_node.text if value_node is not None else ""
                if cell_type == "s" and value:
                    value = shared_strings[int(value)]
            values.append(value or "")
            cells.append({"cell": coordinate, "value": value or ""})
            if value not in {None, ""}:
                non_empty_cells += 1
                extracted_bytes += len(value.encode("utf-8"))
                if extracted_bytes > remaining_output_bytes:
                    raise FileSafetyError(
                        "parsed_output_too_large", "解析结果超过允许上限"
                    )
        rows.append(values)
    return rows, cells, non_empty_cells, has_formula, extracted_bytes


def _ensure_content_budget(content_bytes: int, limits: ProcessingLimits) -> None:
    if content_bytes > limits.max_output_bytes:
        raise FileSafetyError("parsed_output_too_large", "解析结果超过允许上限")
