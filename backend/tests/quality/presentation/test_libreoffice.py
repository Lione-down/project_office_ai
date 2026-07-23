from hashlib import sha256
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError
from pypdf import PdfWriter

from app.services.quality.presentation.libreoffice import (
    LibreOfficeClient,
    LibreOfficeError,
    LibreOfficePage,
    LibreOfficeRequest,
    LibreOfficeRunner,
)


REQUEST_ID = UUID("019b0000-0000-7000-8000-000000000311")
USER_ID = UUID("019b0000-0000-7000-8000-000000000312")
ASSET_ID = UUID("019b0000-0000-7000-8000-000000000313")


async def test_client_verifies_all_pdf_and_preview_artifacts(tmp_path: Path) -> None:
    work = tmp_path / "quality" / str(REQUEST_ID)
    pages = work / "pages"
    pages.mkdir(parents=True)
    pdf = work / "preview.pdf"
    first = pages / "page-0001.png"
    second = pages / "page-0002.png"
    pdf.write_bytes(b"%PDF-synthetic")
    first.write_bytes(b"png-page-one")
    second.write_bytes(b"png-page-two")

    def descriptor(path: Path, key: str) -> dict:
        return {
            "key": key,
            "sha256": sha256(path.read_bytes()).hexdigest(),
            "byte_size": path.stat().st_size,
        }

    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read().decode("utf-8")
        assert "source_path" not in payload
        assert "storage_key" not in payload
        return httpx.Response(
            200,
            json={
                "schema_version": "libreoffice-presentation-response.v1",
                "request_id": str(REQUEST_ID),
                "status": "succeeded",
                "libreoffice_version": "LibreOffice 25.2.3",
                "pdf": descriptor(pdf, f"quality/{REQUEST_ID}/preview.pdf"),
                "pages": [
                    {
                        **descriptor(
                            first,
                            f"quality/{REQUEST_ID}/pages/page-0001.png",
                        ),
                        "page_number": 1,
                        "width": 1280,
                        "height": 720,
                    },
                    {
                        **descriptor(
                            second,
                            f"quality/{REQUEST_ID}/pages/page-0002.png",
                        ),
                        "page_number": 2,
                        "width": 1280,
                        "height": 720,
                    },
                ],
            },
        )

    client = LibreOfficeClient(
        "http://libreoffice:8081",
        tmp_path,
        transport=httpx.MockTransport(handler),
    )

    result = await client.convert(
        request_id=REQUEST_ID,
        user_id=USER_ID,
        asset_id=ASSET_ID,
        source_sha256="a" * 64,
        source_byte_size=1024,
    )

    assert result.pdf.path == pdf
    assert [page.page_number for page in result.pages] == [1, 2]
    assert result.libreoffice_version == "LibreOffice 25.2.3"


@pytest.mark.parametrize(
    "pdf_key",
    ["../secret.pdf", "/absolute/secret.pdf", "quality/other/preview.pdf"],
)
async def test_client_rejects_path_escape_or_wrong_request(
    tmp_path: Path, pdf_key: str
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "schema_version": "libreoffice-presentation-response.v1",
                "request_id": str(REQUEST_ID),
                "status": "succeeded",
                "libreoffice_version": "LibreOffice 25.2.3",
                "pdf": {
                    "key": pdf_key,
                    "sha256": "a" * 64,
                    "byte_size": 1,
                },
                "pages": [
                    {
                        "key": f"quality/{REQUEST_ID}/pages/page-0001.png",
                        "sha256": "b" * 64,
                        "byte_size": 1,
                        "page_number": 1,
                        "width": 1,
                        "height": 1,
                    }
                ],
            },
        )

    client = LibreOfficeClient(
        "http://libreoffice:8081",
        tmp_path,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LibreOfficeError, match="libreoffice_response_invalid"):
        await client.convert(
            request_id=REQUEST_ID,
            user_id=USER_ID,
            asset_id=ASSET_ID,
            source_sha256="a" * 64,
            source_byte_size=1024,
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "file:///private/libreoffice",
        "http://user:password@libreoffice:8081",
        "http://libreoffice:8081/v1",
    ],
)
def test_client_rejects_unsafe_base_url(tmp_path: Path, base_url: str) -> None:
    with pytest.raises(ValueError, match="LibreOffice base URL is invalid"):
        LibreOfficeClient(base_url, tmp_path)


def test_runner_uses_fixed_asset_path_and_generates_pdf_pages(tmp_path: Path) -> None:
    files_root = tmp_path / "files"
    source = (
        files_root
        / "users"
        / str(USER_ID)
        / "outputs"
        / str(ASSET_ID)
        / "presentation.pptx"
    )
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic-presentation")
    observed_source: list[Path] = []

    def converter(source_path: Path, work_dir: Path) -> tuple[Path, str]:
        observed_source.append(source_path)
        pdf = work_dir / "preview.pdf"
        pdf.write_bytes(b"%PDF-from-libreoffice")
        return pdf, "LibreOffice 25.2.3"

    def preview_renderer(pdf_path: Path, pages_dir: Path) -> list[LibreOfficePage]:
        assert pdf_path.read_bytes().startswith(b"%PDF")
        pages_dir.mkdir()
        image = pages_dir / "page-0001.png"
        image.write_bytes(b"synthetic-png")
        return [LibreOfficePage(image, 1, 1280, 720)]

    runner = LibreOfficeRunner(
        files_root,
        tmp_path / "work",
        converter=converter,
        preview_renderer=preview_renderer,
    )
    request = LibreOfficeRequest(
        schema_version="libreoffice-presentation-request.v1",
        request_id=REQUEST_ID,
        user_id=USER_ID,
        asset_id=ASSET_ID,
        source_sha256=sha256(source.read_bytes()).hexdigest(),
        source_byte_size=source.stat().st_size,
    )

    result = runner.convert(request)

    assert observed_source == [source]
    assert result.pdf.key == f"quality/{REQUEST_ID}/preview.pdf"
    assert result.pages[0].key == (f"quality/{REQUEST_ID}/pages/page-0001.png")
    assert result.pages[0].page_number == 1


def test_runner_replays_completed_request_without_second_conversion(
    tmp_path: Path,
) -> None:
    source = (
        tmp_path
        / "files"
        / "users"
        / str(USER_ID)
        / "outputs"
        / str(ASSET_ID)
        / "presentation.pptx"
    )
    source.parent.mkdir(parents=True)
    source.write_bytes(b"presentation")
    conversion_calls = 0

    def converter(_source: Path, work_dir: Path) -> tuple[Path, str]:
        nonlocal conversion_calls
        conversion_calls += 1
        pdf = work_dir / "preview.pdf"
        pdf.write_bytes(b"%PDF-replay")
        return pdf, "LibreOffice 25.2.3"

    def preview(_pdf: Path, pages_dir: Path) -> list[LibreOfficePage]:
        pages_dir.mkdir()
        page = pages_dir / "page-0001.png"
        page.write_bytes(b"png")
        return [LibreOfficePage(page, 1, 1280, 720)]

    runner = LibreOfficeRunner(
        tmp_path / "files",
        tmp_path / "work",
        converter=converter,
        preview_renderer=preview,
    )
    request = LibreOfficeRequest(
        schema_version="libreoffice-presentation-request.v1",
        request_id=REQUEST_ID,
        user_id=USER_ID,
        asset_id=ASSET_ID,
        source_sha256=sha256(source.read_bytes()).hexdigest(),
        source_byte_size=source.stat().st_size,
    )

    first = runner.convert(request)
    replay = runner.convert(request)

    assert replay == first
    assert conversion_calls == 1


def test_runner_replay_rejects_same_id_with_changed_source(
    tmp_path: Path,
) -> None:
    source = (
        tmp_path
        / "files"
        / "users"
        / str(USER_ID)
        / "outputs"
        / str(ASSET_ID)
        / "presentation.pptx"
    )
    source.parent.mkdir(parents=True)
    source.write_bytes(b"first-presentation")

    def converter(_source: Path, work_dir: Path) -> tuple[Path, str]:
        pdf = work_dir / "preview.pdf"
        pdf.write_bytes(b"%PDF-bound")
        return pdf, "LibreOffice 25.2.3"

    def preview(_pdf: Path, pages_dir: Path) -> list[LibreOfficePage]:
        pages_dir.mkdir()
        page = pages_dir / "page-0001.png"
        page.write_bytes(b"png")
        return [LibreOfficePage(page, 1, 1280, 720)]

    runner = LibreOfficeRunner(
        tmp_path / "files",
        tmp_path / "work",
        converter=converter,
        preview_renderer=preview,
    )
    first = LibreOfficeRequest(
        schema_version="libreoffice-presentation-request.v1",
        request_id=REQUEST_ID,
        user_id=USER_ID,
        asset_id=ASSET_ID,
        source_sha256=sha256(source.read_bytes()).hexdigest(),
        source_byte_size=source.stat().st_size,
    )
    runner.convert(first)
    source.write_bytes(b"changed-presentation")
    changed = first.model_copy(
        update={
            "source_sha256": sha256(source.read_bytes()).hexdigest(),
            "source_byte_size": source.stat().st_size,
        }
    )

    with pytest.raises(LibreOfficeError, match="libreoffice_replay_invalid"):
        runner.convert(changed)


def test_runner_rejects_source_integrity_mismatch(tmp_path: Path) -> None:
    source = (
        tmp_path
        / "files"
        / "users"
        / str(USER_ID)
        / "outputs"
        / str(ASSET_ID)
        / "presentation.pptx"
    )
    source.parent.mkdir(parents=True)
    source.write_bytes(b"tampered")
    runner = LibreOfficeRunner(
        tmp_path / "files",
        tmp_path / "work",
        converter=lambda *_args: pytest.fail("converter must not run"),
        preview_renderer=lambda *_args: pytest.fail("preview must not run"),
    )

    with pytest.raises(LibreOfficeError, match="presentation_source_integrity_failed"):
        runner.convert(
            LibreOfficeRequest(
                schema_version="libreoffice-presentation-request.v1",
                request_id=REQUEST_ID,
                user_id=USER_ID,
                asset_id=ASSET_ID,
                source_sha256="f" * 64,
                source_byte_size=source.stat().st_size,
            )
        )


def test_runner_reads_repaired_variant_from_fixed_quality_path(tmp_path: Path) -> None:
    repaired = (
        tmp_path
        / "files"
        / "users"
        / str(USER_ID)
        / "outputs"
        / str(ASSET_ID)
        / "quality"
        / "repaired.pptx"
    )
    repaired.parent.mkdir(parents=True)
    repaired.write_bytes(b"repaired-presentation")
    observed: list[Path] = []

    def converter(source_path: Path, work_dir: Path) -> tuple[Path, str]:
        observed.append(source_path)
        pdf = work_dir / "preview.pdf"
        pdf.write_bytes(b"%PDF-repaired")
        return pdf, "LibreOffice 25.2.3"

    def preview(pdf_path: Path, pages_dir: Path) -> list[LibreOfficePage]:
        pages_dir.mkdir()
        page = pages_dir / "page-0001.png"
        page.write_bytes(b"png")
        return [LibreOfficePage(page, 1, 1280, 720)]

    runner = LibreOfficeRunner(
        tmp_path / "files",
        tmp_path / "work",
        converter=converter,
        preview_renderer=preview,
    )

    runner.convert(
        LibreOfficeRequest(
            schema_version="libreoffice-presentation-request.v1",
            request_id=REQUEST_ID,
            user_id=USER_ID,
            asset_id=ASSET_ID,
            source_variant="repaired",
            source_sha256=sha256(repaired.read_bytes()).hexdigest(),
            source_byte_size=repaired.stat().st_size,
        )
    )

    assert observed == [repaired]


def test_libreoffice_request_rejects_client_paths() -> None:
    with pytest.raises(ValidationError):
        LibreOfficeRequest.model_validate(
            {
                "schema_version": "libreoffice-presentation-request.v1",
                "request_id": str(REQUEST_ID),
                "user_id": str(USER_ID),
                "asset_id": str(ASSET_ID),
                "source_sha256": "a" * 64,
                "source_byte_size": 1024,
                "source_path": "C:/private/source.pptx",
            }
        )


def test_pdfium_renderer_creates_bounded_png_preview(tmp_path: Path) -> None:
    pdf = tmp_path / "preview.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=960, height=540)
    with pdf.open("wb") as handle:
        writer.write(handle)

    pages = LibreOfficeRunner._render_pdf_pages(pdf, tmp_path / "pages")

    assert len(pages) == 1
    assert pages[0].path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert pages[0].width == 1280
    assert pages[0].height == 720
