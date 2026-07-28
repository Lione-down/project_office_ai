from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import posixpath
import re
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from app.services.quality.presentation.chart_references import (
    chart_references_are_valid,
)
from app.services.quality.presentation.body_density import inspect_body_text_density
from app.services.quality.presentation.contracts import PresentationQualityFinding


PML = "http://schemas.openxmlformats.org/presentationml/2006/main"
DML = "http://schemas.openxmlformats.org/drawingml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CHART = "http://schemas.openxmlformats.org/drawingml/2006/chart"
NS = {"p": PML, "a": DML, "r": REL, "c": CHART}
REL_ID = f"{{{REL}}}id"
REL_EMBED = f"{{{REL}}}embed"
MAX_ARCHIVE_ENTRIES = 10_000
MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
MAX_XML_MEMBER_BYTES = 16 * 1024 * 1024
TITLE_CHARACTER_LIMIT = 80
EVIDENCE_MARKER = re.compile(r"Evidence:\s*([A-Za-z0-9._:,\-\s]+)")
VISIBLE_EVIDENCE_ID = re.compile(r"\be-[a-f0-9]{64}\b")
REFERENCE_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


@dataclass(frozen=True)
class PresentationInspectionResult:
    slide_count: int
    findings: tuple[PresentationQualityFinding, ...]


class _PackageInvalid(RuntimeError):
    pass


class PresentationPackageInspector:
    def inspect(
        self,
        path: str | Path,
        *,
        expected_slide_count: int,
        expected_evidence_ids: set[str],
    ) -> PresentationInspectionResult:
        try:
            with ZipFile(Path(path)) as archive:
                self._validate_archive(archive)
                findings, slide_count, all_text = self._inspect_package(
                    archive, expected_slide_count
                )
        except (BadZipFile, KeyError, OSError, RuntimeError, ValueError):
            return PresentationInspectionResult(
                slide_count=0,
                findings=(
                    self._finding(
                        "ooxml_corrupt",
                        "presentation-ooxml.v1",
                        repairable=False,
                    ),
                ),
            )
        referenced_evidence = self._evidence_references(all_text)
        missing_evidence = sorted(expected_evidence_ids - referenced_evidence)
        if missing_evidence:
            findings.append(
                self._finding(
                    "evidence_reference_missing",
                    "presentation-evidence.v1",
                    evidence_ids=missing_evidence,
                    repairable=False,
                )
            )
        return PresentationInspectionResult(
            slide_count=slide_count,
            findings=self._deduplicate(findings),
        )

    def _inspect_package(
        self, archive: ZipFile, expected_slide_count: int
    ) -> tuple[list[PresentationQualityFinding], int, str]:
        names = set(archive.namelist())
        presentation = self._xml(archive, "ppt/presentation.xml")
        relationships = self._relationships(archive, "ppt/_rels/presentation.xml.rels")
        slide_size = presentation.find("p:sldSz", NS)
        if slide_size is None:
            raise _PackageInvalid()
        width = self._positive_int(slide_size.attrib.get("cx"))
        height = self._positive_int(slide_size.attrib.get("cy"))
        slide_ids = presentation.findall("p:sldIdLst/p:sldId", NS)
        findings: list[PresentationQualityFinding] = []
        if len(slide_ids) != expected_slide_count:
            findings.append(
                self._finding(
                    "slide_missing",
                    "presentation-slide-count.v1",
                    repairable=False,
                )
            )
        all_text: list[str] = []
        for slide_number, slide_id in enumerate(slide_ids, start=1):
            relationship_id = slide_id.attrib.get(REL_ID)
            relationship = relationships.get(relationship_id or "")
            if relationship is None or not relationship["type"].endswith("/slide"):
                findings.append(
                    self._finding(
                        "slide_missing",
                        "presentation-slide-count.v1",
                        slide_number=slide_number,
                        repairable=False,
                    )
                )
                continue
            slide_name = self._resolve_target(
                "ppt/presentation.xml", relationship["target"]
            )
            if slide_name not in names:
                findings.append(
                    self._finding(
                        "slide_missing",
                        "presentation-slide-count.v1",
                        slide_number=slide_number,
                        repairable=False,
                    )
                )
                continue
            slide = self._xml(archive, slide_name)
            slide_text = "\n".join(
                (node.text or "").strip()
                for node in slide.findall(".//a:t", NS)
                if (node.text or "").strip()
            )
            all_text.append(slide_text)
            if VISIBLE_EVIDENCE_ID.search(slide_text):
                findings.append(
                    self._finding(
                        "visible_evidence_reference",
                        "presentation-visible-evidence.v1",
                        slide_number=slide_number,
                        repairable=False,
                    )
                )
            if self._is_blank(slide, slide_text):
                findings.append(
                    self._finding(
                        "blank_slide",
                        "presentation-content.v1",
                        slide_number=slide_number,
                        repairable=False,
                    )
                )
            findings.extend(self._geometry_findings(slide, slide_number, width, height))
            findings.extend(self._title_findings(slide, slide_number))
            findings.extend(inspect_body_text_density(slide, slide_number))
            findings.extend(
                self._relationship_findings(
                    archive, names, slide, slide_name, slide_number
                )
            )
        notes_text = [
            "\n".join(node.text or "" for node in notes.findall(".//a:t", NS))
            for name in sorted(names)
            if name.startswith("ppt/notesSlides/notesSlide") and name.endswith(".xml")
            for notes in (self._xml(archive, name),)
        ]
        return findings, len(slide_ids), "\n".join((*all_text, *notes_text))

    def _relationship_findings(
        self,
        archive: ZipFile,
        names: set[str],
        slide: ElementTree.Element,
        slide_name: str,
        slide_number: int,
    ) -> list[PresentationQualityFinding]:
        relationships = self._relationships(archive, self._rels_name(slide_name), False)
        findings: list[PresentationQualityFinding] = []
        for blip in slide.findall(".//a:blip", NS):
            relationship_id = blip.attrib.get(REL_EMBED)
            relationship = relationships.get(relationship_id or "")
            if (
                relationship is None
                or not relationship["type"].endswith("/image")
                or self._resolve_target(slide_name, relationship["target"]) not in names
            ):
                findings.append(
                    self._finding(
                        "image_missing",
                        "presentation-image.v1",
                        slide_number=slide_number,
                        repairable=False,
                    )
                )
        for chart in slide.findall(".//c:chart", NS):
            relationship = relationships.get(chart.attrib.get(REL_ID, ""))
            chart_name = (
                self._resolve_target(slide_name, relationship["target"])
                if relationship is not None
                else ""
            )
            if (
                relationship is None
                or not relationship["type"].endswith("/chart")
                or chart_name not in names
                or not chart_references_are_valid(
                    archive,
                    chart_name,
                    xml_loader=self._xml,
                    relationships_loader=self._relationships,
                    target_resolver=self._resolve_target,
                    rels_name=self._rels_name,
                    member_reader=self._read_member,
                    archive_validator=self._validate_archive,
                )
            ):
                findings.append(
                    self._finding(
                        "chart_reference_invalid",
                        "presentation-chart-reference.v1",
                        slide_number=slide_number,
                        repairable=False,
                    )
                )
        return findings

    def _geometry_findings(
        self,
        slide: ElementTree.Element,
        slide_number: int,
        width: int,
        height: int,
    ) -> list[PresentationQualityFinding]:
        findings: list[PresentationQualityFinding] = []
        shape_paths = (
            ("p:sp", "p:spPr/a:xfrm"),
            ("p:pic", "p:spPr/a:xfrm"),
            ("p:graphicFrame", "p:xfrm"),
        )
        for shape_path, transform_path in shape_paths:
            for shape in slide.findall(f".//{shape_path}", NS):
                transform = shape.find(transform_path, NS)
                if transform is None:
                    continue
                offset = transform.find("a:off", NS)
                extent = transform.find("a:ext", NS)
                if offset is None or extent is None:
                    continue
                values = (
                    self._int(offset.attrib.get("x")),
                    self._int(offset.attrib.get("y")),
                    self._int(extent.attrib.get("cx")),
                    self._int(extent.attrib.get("cy")),
                )
                x, y, shape_width, shape_height = values
                if (
                    x < 0
                    or y < 0
                    or shape_width <= 0
                    or shape_height <= 0
                    or x + shape_width > width
                    or y + shape_height > height
                ):
                    shape_id = self._shape_id(shape)
                    findings.append(
                        self._finding(
                            "object_out_of_bounds",
                            "presentation-geometry.v1",
                            slide_number=slide_number,
                            shape_id=shape_id,
                            repairable=True,
                        )
                    )
        return findings

    def _title_findings(
        self, slide: ElementTree.Element, slide_number: int
    ) -> list[PresentationQualityFinding]:
        findings: list[PresentationQualityFinding] = []
        for shape in slide.findall(".//p:sp", NS):
            placeholder = shape.find("p:nvSpPr/p:nvPr/p:ph", NS)
            if placeholder is None or placeholder.attrib.get("type") not in {
                "title",
                "ctrTitle",
            }:
                continue
            title = "".join(node.text or "" for node in shape.findall(".//a:t", NS))
            has_autofit = shape.find("p:txBody/a:bodyPr/a:normAutofit", NS) is not None
            if len(title) > TITLE_CHARACTER_LIMIT and not has_autofit:
                findings.append(
                    self._finding(
                        "title_overflow_risk",
                        "presentation-title-fit.v1",
                        slide_number=slide_number,
                        shape_id=self._shape_id(shape),
                        repairable=True,
                    )
                )
        return findings

    def _validate_archive(
        self, archive: ZipFile, *, require_presentation: bool = True
    ) -> None:
        members = archive.infolist()
        if len(members) > MAX_ARCHIVE_ENTRIES:
            raise _PackageInvalid()
        total_uncompressed = 0
        for member in members:
            path = PurePosixPath(member.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or member.flag_bits & 0x1:
                raise _PackageInvalid()
            total_uncompressed += member.file_size
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise _PackageInvalid()
            if (
                member.file_size
                and member.file_size / max(member.compress_size, 1)
                > MAX_COMPRESSION_RATIO
            ):
                raise _PackageInvalid()
        if archive.testzip() is not None:
            raise _PackageInvalid()
        if require_presentation:
            content_types = self._xml(archive, "[Content_Types].xml")
            declared = {
                value
                for element in content_types.iter()
                if (value := element.attrib.get("ContentType"))
            }
            if not any(
                "presentationml.presentation.main+xml" in item for item in declared
            ):
                raise _PackageInvalid()
            if "ppt/presentation.xml" not in archive.namelist():
                raise _PackageInvalid()

    def _xml(self, archive: ZipFile, name: str) -> ElementTree.Element:
        payload = self._read_member(archive, name)
        if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
            raise _PackageInvalid()
        try:
            return ElementTree.fromstring(payload)
        except ElementTree.ParseError as exception:
            raise _PackageInvalid() from exception

    @staticmethod
    def _read_member(archive: ZipFile, name: str) -> bytes:
        member = archive.getinfo(name)
        if member.file_size > MAX_XML_MEMBER_BYTES:
            raise _PackageInvalid()
        with archive.open(member) as handle:
            payload = handle.read(MAX_XML_MEMBER_BYTES + 1)
        if len(payload) > MAX_XML_MEMBER_BYTES:
            raise _PackageInvalid()
        return payload

    def _relationships(
        self, archive: ZipFile, name: str, required: bool = True
    ) -> dict[str, dict[str, str]]:
        if name not in archive.namelist():
            if required:
                raise _PackageInvalid()
            return {}
        root = self._xml(archive, name)
        relationships: dict[str, dict[str, str]] = {}
        for item in root.findall(f"{{{PKG_REL}}}Relationship"):
            if item.attrib.get("TargetMode") == "External":
                raise _PackageInvalid()
            relationship_id = item.attrib.get("Id")
            target = item.attrib.get("Target")
            relationship_type = item.attrib.get("Type")
            if not relationship_id or not target or not relationship_type:
                raise _PackageInvalid()
            relationships[relationship_id] = {
                "target": target,
                "type": relationship_type,
            }
        return relationships

    @staticmethod
    def _resolve_target(source_name: str, target: str) -> str:
        normalized_target = target.replace("\\", "/")
        if normalized_target.startswith("/"):
            resolved = posixpath.normpath(normalized_target.lstrip("/"))
        else:
            resolved = posixpath.normpath(
                posixpath.join(posixpath.dirname(source_name), normalized_target)
            )
        if resolved.startswith("../") or resolved in {"", ".", ".."}:
            raise _PackageInvalid()
        return resolved

    @staticmethod
    def _rels_name(part_name: str) -> str:
        path = PurePosixPath(part_name)
        return str(path.parent / "_rels" / f"{path.name}.rels")

    @staticmethod
    def _is_blank(slide: ElementTree.Element, text: str) -> bool:
        return not text and not any(
            slide.find(path, NS) is not None
            for path in (".//a:blip", ".//a:tbl", ".//c:chart")
        )

    @staticmethod
    def _evidence_references(text: str) -> set[str]:
        references: set[str] = set()
        for marker in EVIDENCE_MARKER.findall(text):
            references.update(REFERENCE_TOKEN.findall(marker))
        return references

    @staticmethod
    def _shape_id(shape: ElementTree.Element) -> str | None:
        metadata = shape.find(".//p:cNvPr", NS)
        return metadata.attrib.get("id") if metadata is not None else None

    @staticmethod
    def _int(value: str | None) -> int:
        if value is None:
            raise _PackageInvalid()
        return int(value)

    def _positive_int(self, value: str | None) -> int:
        result = self._int(value)
        if result <= 0:
            raise _PackageInvalid()
        return result

    @staticmethod
    def _finding(
        code: str,
        rule_version: str,
        *,
        slide_number: int | None = None,
        shape_id: str | None = None,
        evidence_ids: list[str] | None = None,
        repairable: bool,
    ) -> PresentationQualityFinding:
        return PresentationQualityFinding(
            code=code,
            severity="blocker",
            rule_version=rule_version,
            slide_number=slide_number,
            shape_id=shape_id,
            evidence_ids=evidence_ids or [],
            repairable=repairable,
        )

    @staticmethod
    def _deduplicate(
        findings: list[PresentationQualityFinding],
    ) -> tuple[PresentationQualityFinding, ...]:
        result: list[PresentationQualityFinding] = []
        seen: set[tuple] = set()
        for finding in findings:
            key = (
                finding.code,
                finding.slide_number,
                finding.shape_id,
                tuple(finding.evidence_ids),
            )
            if key not in seen:
                seen.add(key)
                result.append(finding)
        return tuple(result)
