from __future__ import annotations

from pathlib import Path, PurePosixPath
import re
from zipfile import BadZipFile, ZipFile

from defusedxml import ElementTree

from app.services.golden.contracts import OfficeArtifactInspection


PII_PATTERNS = (
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)0\d{2,3}[- ]?\d{7,8}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
)
SAFE_AUTHORS = {"", "Office AI"}
TEXT_ELEMENTS = {"t", "creator", "lastModifiedBy", "title", "subject", "company"}
MAX_ENTRIES = 10_000
MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024


def inspect_office_artifact(path: str | Path) -> OfficeArtifactInspection:
    pii_count = 0
    external_count = 0
    macro_count = 0
    embedded_count = 0
    unsafe_author = False
    try:
        with ZipFile(Path(path)) as archive:
            members = archive.infolist()
            if len(members) > MAX_ENTRIES or archive.testzip() is not None:
                raise ValueError("invalid_package")
            total = 0
            for member in members:
                package_path = PurePosixPath(member.filename.replace("\\", "/"))
                if package_path.is_absolute() or ".." in package_path.parts:
                    raise ValueError("invalid_package")
                total += member.file_size
                if total > MAX_UNCOMPRESSED_BYTES:
                    raise ValueError("invalid_package")
                lowered = member.filename.casefold()
                if lowered.endswith("vbaproject.bin"):
                    macro_count += 1
                if lowered.startswith(
                    ("ppt/embeddings/", "xl/embeddings/")
                ) and not lowered.endswith("/"):
                    embedded_count += 1
                if not lowered.endswith((".xml", ".rels")):
                    continue
                payload = archive.read(member)
                if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
                    raise ValueError("invalid_package")
                root = ElementTree.fromstring(payload)
                for element in root.iter():
                    local_name = element.tag.rsplit("}", 1)[-1]
                    if (
                        local_name == "Relationship"
                        and element.attrib.get("TargetMode") == "External"
                    ):
                        external_count += 1
                    if local_name not in TEXT_ELEMENTS:
                        continue
                    text = (element.text or "").strip()
                    pii_count += sum(
                        len(pattern.findall(text)) for pattern in PII_PATTERNS
                    )
                    if local_name in {"creator", "lastModifiedBy"}:
                        unsafe_author = unsafe_author or text not in SAFE_AUTHORS
    except (BadZipFile, OSError, ValueError, ElementTree.ParseError):
        return OfficeArtifactInspection(
            is_safe=False,
            potential_pii_count=1,
            external_relationship_count=0,
            macro_payload_count=0,
            embedded_object_count=0,
            author_metadata_present=False,
        )
    is_safe = not any(
        (pii_count, external_count, macro_count, embedded_count, unsafe_author)
    )
    return OfficeArtifactInspection(
        is_safe=is_safe,
        potential_pii_count=pii_count,
        external_relationship_count=external_count,
        macro_payload_count=macro_count,
        embedded_object_count=embedded_count,
        author_metadata_present=unsafe_author,
    )
