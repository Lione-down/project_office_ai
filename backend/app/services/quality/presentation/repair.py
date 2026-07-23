from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import posixpath
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from app.services.quality.presentation.contracts import PresentationQualityFinding
from app.services.quality.presentation.inspector import DML, PKG_REL, PML, REL, NS


ElementTree.register_namespace("a", DML)
ElementTree.register_namespace("p", PML)
ElementTree.register_namespace("r", REL)


class PresentationRepairError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepairedPresentation:
    path: Path
    sha256: str
    byte_size: int
    warnings: tuple[PresentationQualityFinding, ...]


class PresentationDeterministicRepair:
    _repairable_codes = frozenset({"object_out_of_bounds", "title_overflow_risk"})

    def repair(
        self,
        source: str | Path,
        target: str | Path,
        findings: tuple[PresentationQualityFinding, ...],
    ) -> RepairedPresentation:
        source_path = Path(source).resolve()
        target_path = Path(target).resolve()
        blockers = [finding for finding in findings if finding.severity == "blocker"]
        if not blockers or any(
            not finding.repairable or finding.code not in self._repairable_codes
            for finding in blockers
        ):
            raise PresentationRepairError("presentation_repair_not_applicable")
        if source_path == target_path or target_path.exists():
            raise PresentationRepairError("presentation_repair_target_invalid")
        repairs_by_slide: dict[int, list[PresentationQualityFinding]] = {}
        for finding in blockers:
            if finding.slide_number is None:
                raise PresentationRepairError("presentation_repair_not_applicable")
            repairs_by_slide.setdefault(finding.slide_number, []).append(finding)
        temporary = target_path.with_suffix(f"{target_path.suffix}.tmp")
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with ZipFile(source_path) as source_archive:
                replacements, warnings = self._replacements(
                    source_archive, repairs_by_slide
                )
                with ZipFile(temporary, "x", ZIP_DEFLATED, compresslevel=9) as target:
                    for member in sorted(
                        source_archive.infolist(), key=lambda item: item.filename
                    ):
                        if member.is_dir():
                            continue
                        payload = replacements.get(
                            member.filename, source_archive.read(member)
                        )
                        target.writestr(self._deterministic_info(member), payload)
            os.replace(temporary, target_path)
        except PresentationRepairError:
            temporary.unlink(missing_ok=True)
            raise
        except Exception as exception:
            temporary.unlink(missing_ok=True)
            raise PresentationRepairError("presentation_repair_failed") from exception
        digest = sha256(target_path.read_bytes()).hexdigest()
        return RepairedPresentation(
            path=target_path,
            sha256=digest,
            byte_size=target_path.stat().st_size,
            warnings=tuple(warnings),
        )

    def _replacements(
        self,
        archive: ZipFile,
        repairs_by_slide: dict[int, list[PresentationQualityFinding]],
    ) -> tuple[dict[str, bytes], list[PresentationQualityFinding]]:
        presentation = ElementTree.fromstring(archive.read("ppt/presentation.xml"))
        slide_size = presentation.find("p:sldSz", NS)
        if slide_size is None:
            raise PresentationRepairError("presentation_repair_failed")
        width = int(slide_size.attrib["cx"])
        height = int(slide_size.attrib["cy"])
        relationships = self._relationship_targets(
            archive, "ppt/_rels/presentation.xml.rels"
        )
        slide_ids = presentation.findall("p:sldIdLst/p:sldId", NS)
        replacements: dict[str, bytes] = {}
        warnings: list[PresentationQualityFinding] = []
        for slide_number, slide_findings in repairs_by_slide.items():
            if not 1 <= slide_number <= len(slide_ids):
                raise PresentationRepairError("presentation_repair_failed")
            relationship_id = slide_ids[slide_number - 1].attrib.get(f"{{{REL}}}id")
            target = relationships.get(relationship_id or "")
            if target is None:
                raise PresentationRepairError("presentation_repair_failed")
            slide_name = posixpath.normpath(posixpath.join("ppt", target))
            slide = ElementTree.fromstring(archive.read(slide_name))
            for finding in slide_findings:
                if finding.code == "object_out_of_bounds":
                    self._repair_geometry(slide, finding.shape_id, width, height)
                    warning_code = "object_bounds_repaired"
                else:
                    self._repair_title(slide, finding.shape_id)
                    warning_code = "title_autofit_applied"
                warnings.append(
                    PresentationQualityFinding(
                        code=warning_code,
                        severity="warning",
                        rule_version=finding.rule_version,
                        slide_number=finding.slide_number,
                        shape_id=finding.shape_id,
                        evidence_ids=finding.evidence_ids,
                        repairable=False,
                    )
                )
            replacements[slide_name] = ElementTree.tostring(
                slide, encoding="utf-8", xml_declaration=True
            )
        return replacements, warnings

    def _repair_geometry(
        self,
        slide: ElementTree.Element,
        shape_id: str | None,
        width: int,
        height: int,
    ) -> None:
        shape = self._shape(slide, shape_id)
        transform = (
            shape.find("p:xfrm", NS)
            if shape.tag == f"{{{PML}}}graphicFrame"
            else shape.find("p:spPr/a:xfrm", NS)
        )
        if transform is None:
            raise PresentationRepairError("presentation_repair_failed")
        offset = transform.find("a:off", NS)
        extent = transform.find("a:ext", NS)
        if offset is None or extent is None:
            raise PresentationRepairError("presentation_repair_failed")
        x = max(0, min(int(offset.attrib["x"]), width - 1))
        y = max(0, min(int(offset.attrib["y"]), height - 1))
        shape_width = max(1, min(int(extent.attrib["cx"]), width - x))
        shape_height = max(1, min(int(extent.attrib["cy"]), height - y))
        offset.attrib.update({"x": str(x), "y": str(y)})
        extent.attrib.update({"cx": str(shape_width), "cy": str(shape_height)})

    def _repair_title(self, slide: ElementTree.Element, shape_id: str | None) -> None:
        shape = self._shape(slide, shape_id)
        body = shape.find("p:txBody/a:bodyPr", NS)
        if body is None:
            raise PresentationRepairError("presentation_repair_failed")
        for child in list(body):
            if child.tag in {
                f"{{{DML}}}noAutofit",
                f"{{{DML}}}spAutoFit",
                f"{{{DML}}}normAutofit",
            }:
                body.remove(child)
        title_length = len(
            "".join(node.text or "" for node in shape.findall(".//a:t", NS))
        )
        font_scale = max(50_000, min(100_000, 8_000_000 // max(title_length, 1)))
        ElementTree.SubElement(
            body,
            f"{{{DML}}}normAutofit",
            {
                "fontScale": str(font_scale),
                "lnSpcReduction": "10000",
            },
        )

    def _shape(
        self, slide: ElementTree.Element, shape_id: str | None
    ) -> ElementTree.Element:
        if shape_id is None:
            raise PresentationRepairError("presentation_repair_failed")
        for shape_name in ("sp", "pic", "graphicFrame"):
            for shape in slide.findall(f".//p:{shape_name}", NS):
                metadata = shape.find(".//p:cNvPr", NS)
                if metadata is not None and metadata.attrib.get("id") == shape_id:
                    return shape
        raise PresentationRepairError("presentation_repair_failed")

    @staticmethod
    def _relationship_targets(archive: ZipFile, name: str) -> dict[str, str]:
        root = ElementTree.fromstring(archive.read(name))
        return {
            item.attrib["Id"]: item.attrib["Target"]
            for item in root.findall(f"{{{PKG_REL}}}Relationship")
        }

    @staticmethod
    def _deterministic_info(source: ZipInfo) -> ZipInfo:
        target = ZipInfo(source.filename, date_time=(1980, 1, 1, 0, 0, 0))
        target.compress_type = ZIP_DEFLATED
        target.external_attr = source.external_attr
        target.create_system = source.create_system
        return target
