from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.quality.presentation.contracts import Sha256
from app.services.quality.presentation.pdf_preview import render_pdf_pages
from app.services.quality.presentation.libreoffice_replay import (
    load_completed,
    write_manifest,
)


MAX_PRESENTATION_BYTES = 100 * 1024 * 1024
MAX_PREVIEW_BYTES = 20 * 1024 * 1024


class LibreOfficeError(RuntimeError):
    def __init__(self, error_code: str, *, retryable: bool) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.retryable = retryable


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LibreOfficeRequest(StrictModel):
    schema_version: Literal["libreoffice-presentation-request.v1"]
    request_id: Annotated[UUID, Field(strict=False)]
    user_id: Annotated[UUID, Field(strict=False)]
    asset_id: Annotated[UUID, Field(strict=False)]
    source_variant: Literal["original", "repaired"] = "original"
    source_sha256: Sha256
    source_byte_size: Annotated[int, Field(gt=0, le=MAX_PRESENTATION_BYTES)]


class ArtifactDescriptor(StrictModel):
    key: Annotated[str, Field(min_length=1, max_length=512)]
    sha256: Sha256
    byte_size: Annotated[int, Field(gt=0, le=MAX_PRESENTATION_BYTES)]


class PageDescriptor(ArtifactDescriptor):
    page_number: Annotated[int, Field(ge=1, le=30)]
    width: Annotated[int, Field(ge=1, le=4096)]
    height: Annotated[int, Field(ge=1, le=4096)]


class LibreOfficeResponse(StrictModel):
    schema_version: Literal["libreoffice-presentation-response.v1"]
    request_id: Annotated[UUID, Field(strict=False)]
    status: Literal["succeeded"]
    libreoffice_version: Annotated[str, Field(min_length=1, max_length=64)]
    pdf: ArtifactDescriptor
    pages: Annotated[list[PageDescriptor], Field(min_length=1, max_length=30)]


@dataclass(frozen=True)
class LibreOfficeArtifact:
    path: Path
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class LibreOfficePage:
    path: Path
    page_number: int
    width: int
    height: int
    sha256: str | None = None
    byte_size: int | None = None


@dataclass(frozen=True)
class LibreOfficeConversion:
    libreoffice_version: str
    pdf: LibreOfficeArtifact
    pages: tuple[LibreOfficePage, ...]


class LibreOfficeClient:
    def __init__(
        self,
        base_url: str,
        work_root: str | Path,
        *,
        timeout_seconds: float = 120,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("LibreOffice base URL is invalid")
        self._base_url = base_url.rstrip("/")
        self._work_root = Path(work_root).resolve()
        self._timeout = timeout_seconds
        self._transport = transport

    async def convert(
        self,
        *,
        request_id: UUID,
        user_id: UUID,
        asset_id: UUID,
        source_sha256: str,
        source_byte_size: int,
        source_variant: Literal["original", "repaired"] = "original",
    ) -> LibreOfficeConversion:
        request = LibreOfficeRequest(
            schema_version="libreoffice-presentation-request.v1",
            request_id=request_id,
            user_id=user_id,
            asset_id=asset_id,
            source_variant=source_variant,
            source_sha256=source_sha256,
            source_byte_size=source_byte_size,
        )
        content = json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            try:
                async with client.stream(
                    "POST",
                    "/v1/presentation/convert",
                    content=content,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    status_code = response.status_code
                    content_type = response.headers.get("content-type", "")
                    response_bytes = bytearray()
                    async for chunk in response.aiter_bytes():
                        response_bytes.extend(chunk)
                        if len(response_bytes) > 64 * 1024:
                            raise self._invalid_response()
            except httpx.HTTPError as exception:
                raise LibreOfficeError(
                    "libreoffice_unavailable", retryable=True
                ) from exception
        if content_type.split(";")[0].strip() != "application/json":
            raise self._invalid_response()
        try:
            body = json.loads(response_bytes)
        except (UnicodeDecodeError, ValueError) as exception:
            raise self._invalid_response() from exception
        if status_code != 200:
            raise self._remote_error(body)
        try:
            response = LibreOfficeResponse.model_validate(body)
        except ValidationError as exception:
            raise self._invalid_response() from exception
        if response.request_id != request_id:
            raise self._invalid_response()
        pdf_path = self._resolve_key(
            request_id, response.pdf.key, expected_name=("preview.pdf",)
        )
        pdf_digest, pdf_size = self._digest(pdf_path, MAX_PRESENTATION_BYTES)
        if pdf_digest != response.pdf.sha256 or pdf_size != response.pdf.byte_size:
            raise self._invalid_response()
        pages: list[LibreOfficePage] = []
        for expected_number, page in enumerate(response.pages, start=1):
            if page.page_number != expected_number:
                raise self._invalid_response()
            page_path = self._resolve_key(
                request_id,
                page.key,
                expected_name=("pages", f"page-{expected_number:04d}.png"),
            )
            digest, byte_size = self._digest(page_path, MAX_PREVIEW_BYTES)
            if digest != page.sha256 or byte_size != page.byte_size:
                raise self._invalid_response()
            pages.append(
                LibreOfficePage(
                    path=page_path,
                    page_number=page.page_number,
                    width=page.width,
                    height=page.height,
                    sha256=digest,
                    byte_size=byte_size,
                )
            )
        return LibreOfficeConversion(
            libreoffice_version=response.libreoffice_version,
            pdf=LibreOfficeArtifact(pdf_path, pdf_digest, pdf_size),
            pages=tuple(pages),
        )

    def _resolve_key(
        self, request_id: UUID, key_value: str, *, expected_name: tuple[str, ...]
    ) -> Path:
        key = PurePosixPath(key_value)
        if key.is_absolute() or key.parts != (
            "quality",
            str(request_id),
            *expected_name,
        ):
            raise self._invalid_response()
        path = self._work_root.joinpath(*key.parts).resolve()
        if not path.is_relative_to(self._work_root) or not path.is_file():
            raise self._invalid_response()
        return path

    @staticmethod
    def _digest(path: Path, maximum: int) -> tuple[str, int]:
        digest = sha256()
        byte_size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                byte_size += len(chunk)
                if byte_size > maximum:
                    raise LibreOfficeClient._invalid_response()
                digest.update(chunk)
        return digest.hexdigest(), byte_size

    @staticmethod
    def _remote_error(body) -> LibreOfficeError:
        error = body.get("error") if isinstance(body, dict) else None
        if (
            not isinstance(error, dict)
            or not isinstance(error.get("code"), str)
            or not isinstance(error.get("retryable"), bool)
        ):
            return LibreOfficeClient._invalid_response()
        return LibreOfficeError(
            error["code"][:64],
            retryable=error["retryable"],
        )

    @staticmethod
    def _invalid_response() -> LibreOfficeError:
        return LibreOfficeError("libreoffice_response_invalid", retryable=False)


class LibreOfficeRunner:
    _render_pdf_pages = staticmethod(render_pdf_pages)

    def __init__(
        self,
        files_root: str | Path,
        work_root: str | Path,
        *,
        timeout_seconds: float = 120,
        converter: Callable[[Path, Path], tuple[Path, str]] | None = None,
        preview_renderer: Callable[[Path, Path], list[LibreOfficePage]] | None = None,
    ) -> None:
        self._files_root = Path(files_root).resolve()
        self._work_root = Path(work_root).resolve()
        self._timeout = timeout_seconds
        self._converter = converter or self._convert_with_soffice
        self._preview_renderer = preview_renderer or self._render_pdf_pages

    def convert(self, request: LibreOfficeRequest) -> LibreOfficeResponse:
        source = self._source_path(
            request.user_id,
            request.asset_id,
            request.source_variant,
        )
        digest, byte_size = self._digest(source, MAX_PRESENTATION_BYTES)
        if digest != request.source_sha256 or byte_size != request.source_byte_size:
            raise LibreOfficeError(
                "presentation_source_integrity_failed", retryable=False
            )
        work_dir = (self._work_root / "quality" / str(request.request_id)).resolve()
        if not work_dir.is_relative_to(self._work_root):
            raise LibreOfficeError("libreoffice_request_invalid", retryable=False)
        manifest = work_dir / "result.json"
        if manifest.is_file():
            return load_completed(self, request, manifest)
        try:
            work_dir.mkdir(parents=True, exist_ok=False)
            pdf_path, version = self._converter(source, work_dir)
            if pdf_path.resolve() != (work_dir / "preview.pdf").resolve():
                raise LibreOfficeError("libreoffice_output_invalid", retryable=False)
            pages = self._preview_renderer(pdf_path, work_dir / "pages")
            if not pages or len(pages) > 30:
                raise LibreOfficeError("libreoffice_output_invalid", retryable=False)
            pdf = self._descriptor(
                request.request_id,
                pdf_path,
                ("preview.pdf",),
                MAX_PRESENTATION_BYTES,
            )
            page_descriptors = [
                self._page_descriptor(request.request_id, page, index)
                for index, page in enumerate(pages, start=1)
            ]
            response = LibreOfficeResponse(
                schema_version="libreoffice-presentation-response.v1",
                request_id=request.request_id,
                status="succeeded",
                libreoffice_version=version[:64],
                pdf=pdf,
                pages=page_descriptors,
            )
            write_manifest(manifest, request, response)
            return response
        except LibreOfficeError:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise
        except Exception as exception:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise LibreOfficeError(
                "libreoffice_conversion_failed", retryable=False
            ) from exception

    def _source_path(
        self,
        user_id: UUID,
        asset_id: UUID,
        source_variant: Literal["original", "repaired"],
    ) -> Path:
        asset_root = (
            self._files_root / "users" / str(user_id) / "outputs" / str(asset_id)
        )
        path = (
            asset_root / "presentation.pptx"
            if source_variant == "original"
            else asset_root / "quality" / "repaired.pptx"
        ).resolve()
        if not path.is_relative_to(self._files_root) or not path.is_file():
            raise LibreOfficeError("presentation_source_missing", retryable=False)
        return path

    def _convert_with_soffice(self, source: Path, work_dir: Path) -> tuple[Path, str]:
        profile = (work_dir / "profile").resolve().as_uri()
        try:
            process = subprocess.run(
                [
                    "soffice",
                    "--headless",
                    "--nologo",
                    "--nodefault",
                    "--nolockcheck",
                    "--norestore",
                    f"-env:UserInstallation={profile}",
                    "--convert-to",
                    "pdf:impress_pdf_Export",
                    "--outdir",
                    str(work_dir),
                    str(source),
                ],
                check=False,
                timeout=self._timeout,
                capture_output=True,
            )
        except (OSError, subprocess.TimeoutExpired) as exception:
            raise LibreOfficeError(
                "libreoffice_unavailable", retryable=True
            ) from exception
        converted = work_dir / "presentation.pdf"
        if process.returncode != 0 or not converted.is_file():
            raise LibreOfficeError("libreoffice_open_failed", retryable=False)
        preview = work_dir / "preview.pdf"
        os.replace(converted, preview)
        try:
            version_process = subprocess.run(
                ["soffice", "--headless", "--version"],
                check=False,
                timeout=10,
                capture_output=True,
            )
        except (OSError, subprocess.TimeoutExpired):
            version = "LibreOffice unknown"
        else:
            version = (
                version_process.stdout.decode("utf-8", errors="replace").strip()
                or "LibreOffice unknown"
            )
        return preview, version

    def _descriptor(
        self,
        request_id: UUID,
        path: Path,
        suffix: tuple[str, ...],
        maximum: int,
    ) -> ArtifactDescriptor:
        expected = (self._work_root / "quality" / str(request_id)).joinpath(*suffix)
        if path.resolve() != expected.resolve():
            raise LibreOfficeError("libreoffice_output_invalid", retryable=False)
        digest, byte_size = self._digest(path, maximum)
        return ArtifactDescriptor(
            key=PurePosixPath("quality", str(request_id), *suffix).as_posix(),
            sha256=digest,
            byte_size=byte_size,
        )

    def _page_descriptor(
        self, request_id: UUID, page: LibreOfficePage, expected_number: int
    ) -> PageDescriptor:
        if page.page_number != expected_number:
            raise LibreOfficeError("libreoffice_output_invalid", retryable=False)
        suffix = ("pages", f"page-{expected_number:04d}.png")
        artifact = self._descriptor(request_id, page.path, suffix, MAX_PREVIEW_BYTES)
        return PageDescriptor(
            **artifact.model_dump(),
            page_number=page.page_number,
            width=page.width,
            height=page.height,
        )

    @staticmethod
    def _digest(path: Path, maximum: int) -> tuple[str, int]:
        if not path.is_file():
            raise LibreOfficeError("libreoffice_output_missing", retryable=False)
        digest = sha256()
        byte_size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                byte_size += len(chunk)
                if byte_size > maximum:
                    raise LibreOfficeError(
                        "libreoffice_output_too_large", retryable=False
                    )
                digest.update(chunk)
        return digest.hexdigest(), byte_size
