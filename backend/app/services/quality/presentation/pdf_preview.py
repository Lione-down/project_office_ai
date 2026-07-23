from pathlib import Path


def render_pdf_pages(pdf_path: Path, pages_dir: Path):
    from app.services.quality.presentation.libreoffice import (
        LibreOfficeError,
        LibreOfficePage,
    )

    try:
        import pypdfium2 as pdfium
    except ImportError as exception:
        raise LibreOfficeError(
            "pdf_preview_renderer_unavailable", retryable=False
        ) from exception
    pages_dir.mkdir()
    result = []
    document = None
    try:
        document = pdfium.PdfDocument(pdf_path)
        if not 1 <= len(document) <= 30:
            raise LibreOfficeError("libreoffice_page_count_invalid", retryable=False)
        for index in range(len(document)):
            page = document[index]
            bitmap = None
            try:
                width, _height = page.get_size()
                scale = min(2.0, 1280 / max(width, 1))
                bitmap = page.render(scale=scale, rotation=0)
                image = bitmap.to_pil()
                target = pages_dir / f"page-{index + 1:04d}.png"
                image.save(target, format="PNG")
                result.append(
                    LibreOfficePage(
                        path=target,
                        page_number=index + 1,
                        width=image.width,
                        height=image.height,
                    )
                )
            finally:
                if bitmap is not None:
                    bitmap.close()
                page.close()
    except LibreOfficeError:
        raise
    except Exception as exception:
        raise LibreOfficeError(
            "pdf_preview_generation_failed", retryable=False
        ) from exception
    finally:
        if document is not None:
            document.close()
    return result
