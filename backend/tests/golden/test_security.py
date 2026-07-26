from pathlib import Path

from app.services.golden.manifest import load_golden_manifest
from app.services.golden.security import inspect_office_artifact


REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "golden-data/manifests/sales-pilot-v1.json"


def test_tracked_corpus_is_deidentified_and_package_safe() -> None:
    manifest = load_golden_manifest(MANIFEST_PATH, repo_root=REPO_ROOT)

    for artifact in manifest.artifacts:
        result = inspect_office_artifact(REPO_ROOT / artifact.path)
        assert result.is_safe is True
        assert result.potential_pii_count == 0
        assert result.external_relationship_count == 0
        assert result.macro_payload_count == 0
        assert result.embedded_object_count == 0
        assert result.author_metadata_present is False


def test_private_and_sanitized_workbook_hashes_are_distinct() -> None:
    manifest = load_golden_manifest(MANIFEST_PATH, repo_root=REPO_ROOT)

    assert manifest.private_sources[0].sha256 != manifest.input_workbook.sha256
