from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


DOCX_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)
XLSM_TYPE = "application/vnd.ms-excel.sheet.macroEnabled.main+xml"
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"


def write_docx(
    path: Path,
    text: str,
    *,
    unsafe_relationships: bool = False,
    empty_paragraph_prefix: bool = False,
) -> Path:
    empty_paragraph = "<w:p/>" if empty_paragraph_prefix else ""
    document_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{empty_paragraph}<w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>
</w:document>
"""
    content_types = f"""<Types>
<Override PartName="/word/document.xml" ContentType="{DOCX_TYPE}"/>
</Types>"""
    relationships = """<Relationships>
<Relationship Target="https://example.invalid/payload" TargetMode="External"/>
</Relationships>"""
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("word/document.xml", document_xml)
        if unsafe_relationships:
            archive.writestr("word/_rels/document.xml.rels", relationships)
            archive.writestr("word/embeddings/object.bin", b"embedded")
    return path


def write_xlsx(
    path: Path,
    *,
    sheet_count: int = 1,
    cells: list[tuple[str, str, str | None]] | None = None,
    macro_enabled: bool = False,
    unsafe_relationships: bool = False,
) -> Path:
    content_type = XLSM_TYPE if macro_enabled else XLSX_TYPE
    sheet_entries = "".join(
        f'<sheet name="Sheet{index}" sheetId="{index}" r:id="rId{index}"/>'
        for index in range(1, sheet_count + 1)
    )
    workbook = f"""<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>{sheet_entries}</sheets></workbook>"""
    relationships = (
        """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">"""
        + "".join(
            f'<Relationship Id="rId{index}" Target="worksheets/sheet{index}.xml"/>'
            for index in range(1, sheet_count + 1)
        )
        + "</Relationships>"
    )
    rows = []
    for coordinate, value, formula in cells or [("A1", "42", None)]:
        formula_xml = f"<f>{formula}</f>" if formula else ""
        rows.append(
            f'<c r="{coordinate}" t="inlineStr">{formula_xml}<is><t>{value}</t></is></c>'
        )
    worksheet = f'<worksheet><sheetData><row r="1">{"".join(rows)}</row></sheetData></worksheet>'
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            f'<Types><Override PartName="/xl/workbook.xml" ContentType="{content_type}"/></Types>',
        )
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        for index in range(1, sheet_count + 1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", worksheet)
        if macro_enabled:
            archive.writestr("xl/vbaProject.bin", b"macro-must-not-be-read")
        if unsafe_relationships:
            archive.writestr("xl/externalLinks/externalLink1.xml", b"external")
            archive.writestr("xl/embeddings/object.bin", b"embedded")
    return path
