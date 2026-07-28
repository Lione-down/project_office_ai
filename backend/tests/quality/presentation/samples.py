from collections.abc import Iterable
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


PML = "http://schemas.openxmlformats.org/presentationml/2006/main"
DML = "http://schemas.openxmlformats.org/drawingml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CHART = "http://schemas.openxmlformats.org/drawingml/2006/chart"


def write_presentation_sample(
    path: Path,
    *,
    slide_count: int = 3,
    blank_slide: int | None = None,
    overflow_slide: int | None = None,
    missing_image_slide: int | None = None,
    long_title_slide: int | None = None,
    bad_chart_slide: int | None = None,
    dense_body_slide: int | None = None,
    slide_number_placeholder_slide: int | None = None,
    evidence_ids: Iterable[str] = ("ev-revenue",),
    notes_evidence_ids: Iterable[str] = (),
) -> Path:
    slides: list[tuple[str, str]] = []
    extra_members: dict[str, bytes | str] = {}
    presentation_relationships: list[str] = []
    slide_ids: list[str] = []
    for number in range(1, slide_count + 1):
        title = (
            "这是一个用于验证确定性标题自动适配规则的超长中文标题" * 5
            if long_title_slide == number
            else f"Synthetic slide {number}"
        )
        is_blank = blank_slide == number
        shape_x = 12_900_000 if overflow_slide == number else 900_000
        relationship_xml = ""
        visual_xml = ""
        if missing_image_slide == number:
            visual_xml += _picture_xml("rIdImage")
            relationship_xml += _relationship(
                "rIdImage",
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                "../media/missing.png",
            )
        if bad_chart_slide == number:
            visual_xml += _chart_frame_xml("rIdChart")
            relationship_xml += _relationship(
                "rIdChart",
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart",
                "../charts/chart1.xml",
            )
            extra_members["ppt/charts/chart1.xml"] = _chart_xml(
                "'Missing Sheet'!$A$1:$A$2"
            )
            extra_members["ppt/charts/_rels/chart1.xml.rels"] = _relationships(
                _relationship(
                    "rIdWorkbook",
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/package",
                    "../embeddings/workbook1.xlsx",
                )
            )
            extra_members["ppt/embeddings/workbook1.xlsx"] = _workbook_bytes()
        body = f"Evidence: {', '.join(evidence_ids)}"
        if dense_body_slide == number:
            body += "\n" + ("经营分析正文过密，无法在当前文本框中安全展示。" * 120)
        slide_xml = _slide_xml(
            title=title,
            body="" if is_blank else body,
            title_x=shape_x,
            include_content=not is_blank,
            visual_xml=visual_xml,
            include_slide_number=slide_number_placeholder_slide == number,
        )
        slides.append((f"ppt/slides/slide{number}.xml", slide_xml))
        if notes_evidence_ids:
            extra_members[f"ppt/notesSlides/notesSlide{number}.xml"] = _notes_xml(
                notes_evidence_ids
            )
        if relationship_xml:
            extra_members[f"ppt/slides/_rels/slide{number}.xml.rels"] = _relationships(
                relationship_xml
            )
        relationship_id = f"rId{number}"
        slide_ids.append(f'<p:sldId id="{255 + number}" r:id="{relationship_id}"/>')
        presentation_relationships.append(
            _relationship(
                relationship_id,
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
                f"slides/slide{number}.xml",
            )
        )

    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types(slide_count))
        archive.writestr("_rels/.rels", _root_relationships())
        archive.writestr("ppt/presentation.xml", _presentation_xml("".join(slide_ids)))
        archive.writestr(
            "ppt/_rels/presentation.xml.rels",
            _relationships("".join(presentation_relationships)),
        )
        for name, body in slides:
            archive.writestr(name, body)
        for name, body in extra_members.items():
            archive.writestr(name, body)
    return path


def _slide_xml(
    *,
    title: str,
    body: str,
    title_x: int,
    include_content: bool,
    visual_xml: str,
    include_slide_number: bool,
) -> str:
    content = (
        _text_shape_xml(
            shape_id=3,
            name="Body",
            text=body,
            x=900_000,
            y=1_800_000,
            cx=9_000_000,
            cy=900_000,
        )
        if include_content
        else ""
    )
    title_shape = (
        _text_shape_xml(
            shape_id=2,
            name="Title",
            text=title if include_content else "",
            x=title_x,
            y=300_000,
            cx=10_500_000,
            cy=700_000,
            placeholder="title",
        )
        if include_content
        else ""
    )
    slide_number_shape = (
        _text_shape_xml(
            shape_id=25,
            name="Slide Number",
            text="10",
            x=11_800_000,
            y=6_560_000,
            cx=180_000,
            cy=180_000,
            placeholder="sldNum",
        )
        if include_slide_number
        else ""
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="{DML}" xmlns:r="{REL}" xmlns:p="{PML}" xmlns:c="{CHART}">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>
      <a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    {title_shape}{content}{visual_xml}{slide_number_shape}
  </p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def _text_shape_xml(
    *,
    shape_id: int,
    name: str,
    text: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    placeholder: str | None = None,
) -> str:
    placeholder_xml = f'<p:ph type="{placeholder}"/>' if placeholder else ""
    return f"""
<p:sp>
  <p:nvSpPr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvSpPr/>
    <p:nvPr>{placeholder_xml}</p:nvPr></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/>
    </a:xfrm></p:spPr>
  <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="zh-CN" sz="2400"/>
    <a:t>{escape(text)}</a:t></a:r></a:p></p:txBody>
</p:sp>"""


def _picture_xml(relationship_id: str) -> str:
    return f"""
<p:pic>
  <p:nvPicPr><p:cNvPr id="4" name="Picture"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
  <p:blipFill><a:blip r:embed="{relationship_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
  <p:spPr><a:xfrm><a:off x="900000" y="3000000"/><a:ext cx="900000" cy="900000"/>
  </a:xfrm><a:prstGeom prst="rect"/></p:spPr>
</p:pic>"""


def _chart_frame_xml(relationship_id: str) -> str:
    return f"""
<p:graphicFrame>
  <p:nvGraphicFramePr><p:cNvPr id="5" name="Chart"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
  <p:xfrm><a:off x="1800000" y="3000000"/><a:ext cx="4000000" cy="2000000"/></p:xfrm>
  <a:graphic><a:graphicData uri="{CHART}"><c:chart r:id="{relationship_id}"/></a:graphicData></a:graphic>
</p:graphicFrame>"""


def _chart_xml(formula: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<c:chartSpace xmlns:c="{CHART}" xmlns:r="{REL}">
  <c:chart><c:plotArea><c:barChart><c:ser>
    <c:cat><c:strRef><c:f>{escape(formula)}</c:f></c:strRef></c:cat>
    <c:val><c:numRef><c:f>{escape(formula)}</c:f></c:numRef></c:val>
  </c:ser></c:barChart></c:plotArea></c:chart>
  <c:externalData r:id="rIdWorkbook"/>
</c:chartSpace>"""


def _workbook_bytes() -> bytes:
    from io import BytesIO

    target = BytesIO()
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/workbook.xml",
            """<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
            <sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            _relationships(
                _relationship(
                    "rId1",
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
                    "worksheets/sheet1.xml",
                )
            ),
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
            <sheetData><row r="1"><c r="A1"><v>1</v></c></row>
            <row r="2"><c r="A2"><v>2</v></c></row></sheetData></worksheet>""",
        )
    return target.getvalue()


def _presentation_xml(slide_ids: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="{DML}" xmlns:r="{REL}" xmlns:p="{PML}">
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000"/>
</p:presentation>"""


def _notes_xml(evidence_ids: Iterable[str]) -> str:
    evidence = escape(f"Evidence: {', '.join(evidence_ids)}")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:notes xmlns:a="{DML}" xmlns:r="{REL}" xmlns:p="{PML}">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>
      <a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    <p:sp><p:nvSpPr><p:cNvPr id="2" name="Notes"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r>
        <a:t>{evidence}</a:t></a:r></a:p></p:txBody></p:sp>
  </p:spTree></p:cSld>
</p:notes>"""


def _content_types(slide_count: int) -> str:
    overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{number}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.'
        f'presentationml.slide+xml"/>'
        for number in range(1, slide_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml"
    ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  {overrides}
</Types>"""


def _root_relationships() -> str:
    return _relationships(
        _relationship(
            "rId1",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
            "ppt/presentation.xml",
        )
    )


def _relationships(body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="{PKG_REL}">{body}</Relationships>"""


def _relationship(relationship_id: str, relationship_type: str, target: str) -> str:
    return (
        f'<Relationship Id="{relationship_id}" Type="{relationship_type}" '
        f'Target="{target}"/>'
    )
