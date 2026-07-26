from pathlib import Path

import pytest

from app.services.golden.contracts import GoldenManifestError
from app.services.golden.manifest import load_golden_manifest


REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "golden-data/manifests/sales-pilot-v1.json"


def test_manifest_declares_authorized_single_case_pilot() -> None:
    manifest = load_golden_manifest(MANIFEST_PATH, repo_root=REPO_ROOT)

    assert manifest.case_id == "sales-pilot-v1"
    assert manifest.authorization.confirmed is True
    assert manifest.authorization.confirmed_on.isoformat() == "2026-07-26"
    assert manifest.coverage.available_cases == 1
    assert manifest.coverage.planned_cases == 10
    assert manifest.coverage.label == "1/10 pilot"
    assert manifest.repetitions.presentation == 20
    assert manifest.repetitions.spreadsheet == 20
    assert manifest.expected_metrics
    assert all(
        metric.source == "system_derived_from_authorized_source"
        for metric in manifest.expected_metrics
    )


def test_manifest_only_allows_tracked_golden_paths() -> None:
    manifest = load_golden_manifest(MANIFEST_PATH, repo_root=REPO_ROOT)

    assert manifest.input_workbook.path.startswith("golden-data/inputs/")
    assert manifest.expected_presentation.path.startswith("golden-data/expected/")
    assert manifest.expected_workbook.path.startswith("golden-data/expected/")
    assert all("private" not in item.path.casefold() for item in manifest.artifacts)


def test_manifest_rejects_private_artifact_path(tmp_path: Path) -> None:
    payload = MANIFEST_PATH.read_text(encoding="utf-8").replace(
        "golden-data/inputs/sales-pilot-v1.xlsx",
        "golden-data/private/source.xlsx",
    )
    invalid = tmp_path / "manifest.json"
    invalid.write_text(payload, encoding="utf-8")

    with pytest.raises(GoldenManifestError, match="golden_path_invalid"):
        load_golden_manifest(invalid, repo_root=REPO_ROOT)
