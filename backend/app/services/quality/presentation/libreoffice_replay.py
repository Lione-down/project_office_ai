import json
import os
from pathlib import Path, PurePosixPath


def load_completed(runner, request, manifest: Path):
    from app.services.quality.presentation.libreoffice import (
        LibreOfficeError,
        LibreOfficePage,
        LibreOfficeRequest,
        LibreOfficeResponse,
        MAX_PRESENTATION_BYTES,
    )

    try:
        payload = manifest.read_bytes()
        if not payload or len(payload) > 64 * 1024:
            raise ValueError
        value = json.loads(payload)
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "request",
            "response",
        }:
            raise ValueError
        if value["schema_version"] != "libreoffice-completion.v1":
            raise ValueError
        stored_request = LibreOfficeRequest.model_validate(value["request"])
        response = LibreOfficeResponse.model_validate(value["response"])
        if stored_request != request or response.request_id != request.request_id:
            raise ValueError
        pdf_path = runner._work_root.joinpath(*PurePosixPath(response.pdf.key).parts)
        actual_pdf = runner._descriptor(
            request.request_id,
            pdf_path,
            ("preview.pdf",),
            MAX_PRESENTATION_BYTES,
        )
        if actual_pdf != response.pdf:
            raise ValueError
        for index, page in enumerate(response.pages, start=1):
            path = runner._work_root.joinpath(*PurePosixPath(page.key).parts)
            actual = runner._page_descriptor(
                request.request_id,
                LibreOfficePage(
                    path,
                    page.page_number,
                    page.width,
                    page.height,
                ),
                index,
            )
            if actual != page:
                raise ValueError
        return response
    except Exception as exception:
        raise LibreOfficeError(
            "libreoffice_replay_invalid", retryable=False
        ) from exception


def write_manifest(manifest: Path, request, response) -> None:
    payload = json.dumps(
        {
            "schema_version": "libreoffice-completion.v1",
            "request": request.model_dump(mode="json"),
            "response": response.model_dump(mode="json"),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    temporary = manifest.with_suffix(".tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, manifest)
