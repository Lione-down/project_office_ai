from io import BytesIO
import re
from zipfile import BadZipFile, ZipFile


REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CHART = "http://schemas.openxmlformats.org/drawingml/2006/chart"
SML = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"c": CHART}
REL_ID = f"{{{REL}}}id"
MAX_CHART_RANGE_CELLS = 10_000
CELL_RANGE = re.compile(
    r"^(?:'((?:[^']|'')+)'|([^!]+))!"
    r"\$?([A-Z]{1,3})\$?([1-9][0-9]*)"
    r"(?::\$?([A-Z]{1,3})\$?([1-9][0-9]*))?$"
)


def chart_references_are_valid(
    archive: ZipFile,
    chart_name: str,
    *,
    xml_loader,
    relationships_loader,
    target_resolver,
    rels_name,
    member_reader,
    archive_validator,
) -> bool:
    try:
        chart = xml_loader(archive, chart_name)
        formulas = [
            (node.text or "").strip()
            for node in chart.findall(".//c:f", NS)
            if (node.text or "").strip()
        ]
        external = chart.find(".//c:externalData", NS)
        relationships = relationships_loader(archive, rels_name(chart_name), False)
        relationship = (
            relationships.get(external.attrib.get(REL_ID, ""))
            if external is not None
            else None
        )
        if not formulas or relationship is None:
            return False
        workbook_name = target_resolver(chart_name, relationship["target"])
        workbook_bytes = member_reader(archive, workbook_name)
        with ZipFile(BytesIO(workbook_bytes)) as workbook:
            archive_validator(workbook, require_presentation=False)
            sheets = _workbook_sheets(
                workbook,
                xml_loader=xml_loader,
                relationships_loader=relationships_loader,
                target_resolver=target_resolver,
            )
            return all(
                _formula_exists(workbook, sheets, formula, xml_loader)
                for formula in formulas
            )
    except (BadZipFile, KeyError, RuntimeError, ValueError):
        return False


def _workbook_sheets(
    workbook: ZipFile,
    *,
    xml_loader,
    relationships_loader,
    target_resolver,
) -> dict[str, str]:
    root = xml_loader(workbook, "xl/workbook.xml")
    relationships = relationships_loader(workbook, "xl/_rels/workbook.xml.rels")
    result: dict[str, str] = {}
    for sheet in root.findall(f".//{{{SML}}}sheet"):
        relationship = relationships.get(sheet.attrib.get(REL_ID, ""))
        name = sheet.attrib.get("name")
        if name and relationship is not None:
            result[name] = target_resolver("xl/workbook.xml", relationship["target"])
    return result


def _formula_exists(
    workbook: ZipFile,
    sheets: dict[str, str],
    formula: str,
    xml_loader,
) -> bool:
    match = CELL_RANGE.fullmatch(formula)
    if match is None:
        return False
    sheet_name = (match.group(1) or match.group(2)).replace("''", "'")
    sheet_path = sheets.get(sheet_name)
    if sheet_path is None:
        return False
    start_column, start_row = match.group(3), int(match.group(4))
    end_column = match.group(5) or start_column
    end_row = int(match.group(6) or start_row)
    start_index = _column_index(start_column)
    end_index = _column_index(end_column)
    cell_count = (end_index - start_index + 1) * (end_row - start_row + 1)
    if (
        end_index < start_index
        or end_row < start_row
        or cell_count > MAX_CHART_RANGE_CELLS
    ):
        return False
    sheet = xml_loader(workbook, sheet_path)
    present = {
        cell.attrib["r"]
        for cell in sheet.findall(f".//{{{SML}}}c")
        if "r" in cell.attrib
    }
    return all(
        f"{_column_name(column)}{row}" in present
        for row in range(start_row, end_row + 1)
        for column in range(start_index, end_index + 1)
    )


def _column_index(name: str) -> int:
    result = 0
    for character in name:
        result = result * 26 + ord(character) - ord("A") + 1
    return result


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result
