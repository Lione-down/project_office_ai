from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.services.quality.spreadsheet.contracts import (
    SpreadsheetQualityFinding,
    SpreadsheetQualityReport,
    SpreadsheetSourceReference,
    SpreadsheetValidationReference,
)


ASSET_ID = UUID("019f6000-0000-7000-8000-000000000001")


def valid_report() -> SpreadsheetQualityReport:
    return SpreadsheetQualityReport(
        schema_version="workbook-quality-report.v1",
        quality_engine_version="spreadsheet-quality.v1",
        source=SpreadsheetSourceReference(
            asset_id=ASSET_ID,
            sha256="a" * 64,
            byte_size=1024,
            plan_sha256="b" * 64,
            renderer_version="excel-renderer.v1",
            template_code="excel.analysis-dashboard.v1",
            template_version="1.0.0",
        ),
        validation=SpreadsheetValidationReference(
            status="passed",
            sha256="c" * 64,
            byte_size=1030,
            report_sha256="d" * 64,
            libreoffice_version="LibreOffice 25.2.3",
            formula_count=12,
            difference_count=0,
        ),
        status="passed",
        download_allowed=True,
        findings=(),
        generated_at=datetime(2026, 7, 23, tzinfo=UTC),
    )


def test_quality_report_is_strict_traceable_and_contains_no_formula_or_path() -> None:
    report = valid_report()

    payload = report.model_dump_json()

    assert report.schema_version == "workbook-quality-report.v1"
    assert report.source.asset_id == ASSET_ID
    assert report.download_allowed is True
    assert "=SUM(" not in payload
    assert "storage_key" not in payload
    assert "C:\\" not in payload


def test_blocked_report_cannot_allow_download() -> None:
    payload = valid_report().model_dump(mode="json")
    payload["status"] = "blocked"
    payload["findings"] = [
        SpreadsheetQualityFinding(
            code="formula_error_ref",
            severity="blocker",
            rule_version="spreadsheet-formula-errors.v1",
        ).model_dump(mode="json")
    ]

    with pytest.raises(ValidationError):
        SpreadsheetQualityReport.model_validate(payload)
