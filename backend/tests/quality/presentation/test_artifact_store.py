from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from app.services.quality.presentation.artifact_store import (
    PresentationQualityArtifactStore,
    PresentationQualityStoreError,
)
from app.services.quality.presentation.contracts import (
    LibreOfficeVerification,
    PresentationOutputReference,
    PresentationPreviewReference,
    PresentationQualityReport,
    PresentationValidatedOutputReference,
)
from app.services.quality.presentation.libreoffice import (
    LibreOfficeArtifact,
    LibreOfficeConversion,
    LibreOfficePage,
)


USER_ID = UUID("019b0000-0000-7000-8000-000000000321")
ASSET_ID = UUID("019b0000-0000-7000-8000-000000000322")


def quality_report(conversion: LibreOfficeConversion) -> PresentationQualityReport:
    return PresentationQualityReport(
        schema_version="presentation-quality-report.v1",
        quality_engine_version="presentation-quality.v1",
        source=PresentationOutputReference(
            asset_id=ASSET_ID,
            sha256="a" * 64,
            byte_size=1024,
            slide_count=1,
            renderer_version="ppt-renderer.v1",
            template_code="ppt.executive-blue.v1",
            template_version="1.0.0",
            plan_sha256="b" * 64,
        ),
        validated_output=PresentationValidatedOutputReference(
            asset_id=ASSET_ID,
            sha256="a" * 64,
            byte_size=1024,
        ),
        status="passed",
        download_allowed=True,
        findings=[],
        libreoffice=LibreOfficeVerification(
            status="passed",
            version=conversion.libreoffice_version,
            pdf_sha256=conversion.pdf.sha256,
            pdf_byte_size=conversion.pdf.byte_size,
            page_count=1,
        ),
        previews=[
            PresentationPreviewReference(
                page_number=1,
                sha256=conversion.pages[0].sha256,
                byte_size=conversion.pages[0].byte_size,
                width=1280,
                height=720,
            )
        ],
        repair_attempt_count=0,
        generated_at=datetime(2026, 7, 23, tzinfo=UTC),
    )


def conversion(tmp_path: Path) -> LibreOfficeConversion:
    pdf = tmp_path / "preview.pdf"
    page = tmp_path / "page-0001.png"
    pdf.write_bytes(b"%PDF-preview")
    page.write_bytes(b"png-preview")
    from hashlib import sha256

    return LibreOfficeConversion(
        libreoffice_version="LibreOffice 25.2.3",
        pdf=LibreOfficeArtifact(
            pdf,
            sha256(pdf.read_bytes()).hexdigest(),
            pdf.stat().st_size,
        ),
        pages=(
            LibreOfficePage(
                page,
                1,
                1280,
                720,
                sha256(page.read_bytes()).hexdigest(),
                page.stat().st_size,
            ),
        ),
    )


def test_store_persists_and_reloads_immutable_report_and_previews(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "files" / "users" / str(USER_ID) / "outputs" / str(ASSET_ID)
    output_dir.mkdir(parents=True)
    current_conversion = conversion(tmp_path)
    report = quality_report(current_conversion)
    store = PresentationQualityArtifactStore(tmp_path / "files")

    stored = store.persist_report(
        USER_ID,
        ASSET_ID,
        report,
        conversion=current_conversion,
    )
    loaded = store.load_report(
        USER_ID,
        ASSET_ID,
        stored.report_key,
        stored.report_sha256,
    )

    assert stored.report_key == (
        f"users/{USER_ID}/outputs/{ASSET_ID}/quality/report.json"
    )
    assert stored.preview_keys == (
        f"users/{USER_ID}/outputs/{ASSET_ID}/quality/preview.pdf",
        f"users/{USER_ID}/outputs/{ASSET_ID}/quality/pages/page-0001.png",
    )
    assert loaded == report
    assert "storage_key" not in stored.report_path.read_text(encoding="utf-8")


def test_store_stages_repair_without_overwrite(tmp_path: Path) -> None:
    output_dir = tmp_path / "files" / "users" / str(USER_ID) / "outputs" / str(ASSET_ID)
    output_dir.mkdir(parents=True)
    source = tmp_path / "repaired.pptx"
    source.write_bytes(b"repaired-one")
    store = PresentationQualityArtifactStore(tmp_path / "files")

    first = store.stage_repaired(USER_ID, ASSET_ID, source)
    replay = store.stage_repaired(USER_ID, ASSET_ID, source)

    assert first == replay
    assert first.key == (f"users/{USER_ID}/outputs/{ASSET_ID}/quality/repaired.pptx")
    source.write_bytes(b"repaired-two")
    with pytest.raises(
        PresentationQualityStoreError, match="quality_artifact_conflict"
    ):
        store.stage_repaired(USER_ID, ASSET_ID, source)
    assert first.path.read_bytes() == b"repaired-one"


def test_store_rejects_report_key_escape(tmp_path: Path) -> None:
    store = PresentationQualityArtifactStore(tmp_path / "files")

    with pytest.raises(
        PresentationQualityStoreError, match="quality_artifact_key_invalid"
    ):
        store.load_report(USER_ID, ASSET_ID, "../report.json", "a" * 64)
