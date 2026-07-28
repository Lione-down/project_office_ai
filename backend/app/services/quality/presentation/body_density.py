from xml.etree import ElementTree

from app.services.quality.presentation.contracts import PresentationQualityFinding


PML = "http://schemas.openxmlformats.org/presentationml/2006/main"
DML = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"p": PML, "a": DML}
IGNORED_PLACEHOLDER_TYPES = {"title", "ctrTitle", "sldNum", "dt", "ftr"}


def inspect_body_text_density(
    slide: ElementTree.Element, slide_number: int
) -> list[PresentationQualityFinding]:
    findings: list[PresentationQualityFinding] = []
    for shape in slide.findall(".//p:sp", NS):
        placeholder = shape.find("p:nvSpPr/p:nvPr/p:ph", NS)
        if (
            placeholder is not None
            and placeholder.attrib.get("type") in IGNORED_PLACEHOLDER_TYPES
        ):
            continue
        text = "".join(node.text or "" for node in shape.findall(".//a:t", NS))
        if not text.strip():
            continue
        body = shape.find("p:txBody/a:bodyPr", NS)
        transform = shape.find("p:spPr/a:xfrm", NS)
        extent = transform.find("a:ext", NS) if transform is not None else None
        if body is None or extent is None or body.find("a:normAutofit", NS) is not None:
            continue
        width = _positive_int(extent.attrib.get("cx")) / 914_400
        height = _positive_int(extent.attrib.get("cy")) / 914_400
        sizes = [
            int(value)
            for node in shape.findall(".//a:rPr", NS)
            if (value := node.attrib.get("sz")) is not None
        ]
        font_size = max(sizes, default=1_800) / 100
        line_capacity = max(1.0, height * 72 / (font_size * 1.25))
        character_capacity = max(1.0, width * 72 / font_size)
        safe_capacity = line_capacity * character_capacity * 0.75
        if len(text) > safe_capacity:
            findings.append(
                PresentationQualityFinding(
                    code="body_text_overflow_risk",
                    severity="blocker",
                    rule_version="presentation-body-fit.v1",
                    slide_number=slide_number,
                    shape_id=_shape_id(shape),
                    evidence_ids=[],
                    repairable=False,
                )
            )
    return findings


def _positive_int(value: str | None) -> int:
    if value is None:
        raise ValueError("positive integer is required")
    result = int(value)
    if result <= 0:
        raise ValueError("positive integer is required")
    return result


def _shape_id(shape: ElementTree.Element) -> str | None:
    metadata = shape.find(".//p:cNvPr", NS)
    return metadata.attrib.get("id") if metadata is not None else None
