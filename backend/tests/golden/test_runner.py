import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from app.services.golden.contracts import GoldenRegressionError
from app.services.golden.runner import (
    GoldenRegressionRunner,
    workbook_structural_sha256,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "golden-data/manifests/sales-pilot-v1.json"


def _write_package(
    path: Path,
    *,
    payload: bytes,
    create_system: int,
    external_attr: int,
) -> None:
    info = ZipInfo("xl/workbook.xml", date_time=(1980, 1, 31, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.create_system = create_system
    info.external_attr = external_attr
    with ZipFile(path, "w") as package:
        package.writestr(info, payload)


def test_workbook_structural_digest_ignores_zip_metadata_and_xml_newlines(
    tmp_path: Path,
) -> None:
    windows = tmp_path / "windows.xlsx"
    linux = tmp_path / "linux.xlsx"
    changed = tmp_path / "changed.xlsx"
    _write_package(
        windows,
        payload=b'<?xml version="1.0"?>\r\n<workbook value="1"/>',
        create_system=0,
        external_attr=0x81B60000,
    )
    _write_package(
        linux,
        payload=b'<?xml version="1.0"?>\n<workbook value="1"/>',
        create_system=3,
        external_attr=0x81800000,
    )
    _write_package(
        changed,
        payload=b'<?xml version="1.0"?>\n<workbook value="2"/>',
        create_system=3,
        external_attr=0x81800000,
    )

    assert windows.read_bytes() != linux.read_bytes()
    assert workbook_structural_sha256(windows) == workbook_structural_sha256(linux)
    assert workbook_structural_sha256(windows) != workbook_structural_sha256(changed)


def test_runner_repeats_spreadsheet_and_presentation_reference_checks() -> None:
    report = GoldenRegressionRunner(repo_root=REPO_ROOT).run(MANIFEST_PATH)

    assert report.schema_version == "golden-regression-report.v1"
    assert report.case_id == "sales-pilot-v1"
    assert report.coverage_label == "1/10 pilot"
    assert report.status == "passed"
    assert report.spreadsheet_generation_runs == 20
    assert report.presentation_reference_runs == 20
    assert report.presentation_generation_runs == 0
    assert report.presentation_generation_evidence == "ppt_renderer_suite_required"
    assert report.findings == ()


def test_runner_rejects_expected_workbook_hash_drift(tmp_path: Path) -> None:
    expected = REPO_ROOT / "golden-data/expected/sales-pilot-v1.xlsx"
    tampered = tmp_path / expected.name
    tampered.write_bytes(expected.read_bytes() + b"tampered")

    with pytest.raises(
        GoldenRegressionError,
        match="golden_artifact_integrity_failed",
    ):
        GoldenRegressionRunner(repo_root=REPO_ROOT).verify_artifact(
            tampered,
            expected_sha256="0" * 64,
            expected_byte_size=expected.stat().st_size,
        )


def test_runner_rejects_manifest_chart_requirement_drift(tmp_path: Path) -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload["requirements"]["workbook_chart_count"] = 2
    invalid = tmp_path / "manifest.json"
    invalid.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(
        GoldenRegressionError,
        match="golden_requirement_mismatch",
    ):
        GoldenRegressionRunner(repo_root=REPO_ROOT).run(invalid)


def test_structured_report_does_not_expose_paths_or_business_content() -> None:
    report = GoldenRegressionRunner(repo_root=REPO_ROOT).run(MANIFEST_PATH)
    payload = report.model_dump_json()

    assert "golden-data/private" not in payload
    assert "storage_key" not in payload
    assert "formula" not in payload
    assert "current_password" not in payload
    assert "api_key" not in payload
