from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.services.quality.presentation.contracts import (
    LibreOfficeVerification,
    PresentationOutputReference,
    PresentationPreviewReference,
    PresentationQualityFinding,
    PresentationQualityReport,
    PresentationValidatedOutputReference,
)


ASSET_ID = UUID("019b0000-0000-7000-8000-000000000301")


def output_reference() -> PresentationOutputReference:
    return PresentationOutputReference(
        asset_id=ASSET_ID,
        sha256="a" * 64,
        byte_size=1024,
        slide_count=3,
        renderer_version="ppt-renderer.v1",
        template_code="ppt.executive-blue.v1",
        template_version="1.0.0",
        plan_sha256="b" * 64,
    )


def libreoffice_passed() -> LibreOfficeVerification:
    return LibreOfficeVerification(
        status="passed",
        version="LibreOffice 25.2.3",
        pdf_sha256="c" * 64,
        pdf_byte_size=2048,
        page_count=3,
    )


def preview_references() -> list[PresentationPreviewReference]:
    return [
        PresentationPreviewReference(
            page_number=page_number,
            sha256=f"{page_number}" * 64,
            byte_size=512,
            width=1280,
            height=720,
        )
        for page_number in range(1, 4)
    ]


def validated_output(
    *,
    sha256: str = "e" * 64,
    byte_size: int = 1536,
) -> PresentationValidatedOutputReference:
    return PresentationValidatedOutputReference(
        asset_id=ASSET_ID,
        sha256=sha256,
        byte_size=byte_size,
    )


def test_quality_report_v1_links_output_renderer_preview_and_safe_findings() -> None:
    report = PresentationQualityReport(
        schema_version="presentation-quality-report.v1",
        quality_engine_version="presentation-quality.v1",
        source=output_reference(),
        validated_output=validated_output(),
        status="passed_with_warnings",
        download_allowed=True,
        findings=[
            PresentationQualityFinding(
                code="title_autofit_applied",
                severity="warning",
                rule_version="presentation-title-fit.v1",
                slide_number=2,
                shape_id="7",
                evidence_ids=["ev-revenue"],
                repairable=False,
            )
        ],
        libreoffice=libreoffice_passed(),
        previews=preview_references(),
        repair_attempt_count=1,
        repaired_output_sha256="e" * 64,
        generated_at=datetime(2026, 7, 23, tzinfo=UTC),
    )

    payload = report.model_dump(mode="json")

    assert payload["source"]["asset_id"] == str(ASSET_ID)
    assert payload["source"]["renderer_version"] == "ppt-renderer.v1"
    assert payload["status"] == "passed_with_warnings"
    assert payload["download_allowed"] is True
    assert "text" not in payload["findings"][0]
    assert "path" not in payload["findings"][0]
    assert "storage_key" not in payload["findings"][0]


@pytest.mark.parametrize(
    ("changes", "expected_fragment"),
    [
        ({"status": "blocked", "download_allowed": True}, "blocked"),
        ({"status": "passed", "download_allowed": False}, "download"),
        (
            {
                "status": "passed",
                "download_allowed": True,
                "findings": [
                    PresentationQualityFinding(
                        code="ooxml_corrupt",
                        severity="blocker",
                        rule_version="presentation-ooxml.v1",
                        repairable=False,
                    )
                ],
            },
            "blocker",
        ),
        (
            {
                "status": "blocked",
                "download_allowed": False,
                "findings": [],
            },
            "blocker",
        ),
        (
            {
                "repair_attempt_count": 0,
                "repaired_output_sha256": "f" * 64,
            },
            "repair",
        ),
    ],
)
def test_quality_report_rejects_inconsistent_state(
    changes: dict, expected_fragment: str
) -> None:
    values = {
        "schema_version": "presentation-quality-report.v1",
        "quality_engine_version": "presentation-quality.v1",
        "source": output_reference(),
        "validated_output": PresentationValidatedOutputReference(
            asset_id=ASSET_ID,
            sha256="a" * 64,
            byte_size=1024,
        ),
        "status": "passed",
        "download_allowed": True,
        "findings": [],
        "libreoffice": libreoffice_passed(),
        "previews": preview_references(),
        "repair_attempt_count": 0,
        "generated_at": datetime(2026, 7, 23, tzinfo=UTC),
    }
    values.update(changes)

    with pytest.raises(ValidationError, match=expected_fragment):
        PresentationQualityReport(**values)


def test_quality_contract_rejects_unknown_or_sensitive_finding_fields() -> None:
    with pytest.raises(ValidationError):
        PresentationQualityFinding.model_validate(
            {
                "code": "image_missing",
                "severity": "blocker",
                "rule_version": "presentation-image.v1",
                "repairable": False,
                "text": "sensitive slide contents",
                "path": "C:/private/source.pptx",
            }
        )
