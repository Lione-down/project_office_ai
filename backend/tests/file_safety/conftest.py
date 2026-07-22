from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def write_office_archive(
    path: Path,
    *,
    content_type: str,
    members: dict[str, bytes] | None = None,
) -> Path:
    content_types = f"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Override PartName="/payload.xml" ContentType="{content_type}"/>
</Types>
""".encode()
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        for name, payload in (members or {"payload.xml": b"<root/>"}).items():
            archive.writestr(name, payload)
    return path
