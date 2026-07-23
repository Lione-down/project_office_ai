from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services.evidence.contracts import (
    EngineVersion,
    EvidenceManifest,
    EvidenceProcessingError,
)
from app.services.evidence.store import EvidenceManifestStore
from tests.briefs.helpers import ASSET_ID, ASSET_VERSION, USER_ID, source_evidence


def manifest() -> EvidenceManifest:
    return EvidenceManifest(
        schema_version="evidence-manifest.v1",
        manifest_id=f"m-{'4' * 64}",
        asset_id=ASSET_ID,
        asset_version=ASSET_VERSION,
        generated_at=datetime(2026, 7, 23, 23, 0, tzinfo=UTC),
        generator=EngineVersion(name="office-ai-evidence", version="1.0.0"),
        source_parser=EngineVersion(name="xlsx-safe", version="1.0.0"),
        evidence=(source_evidence(),),
    )


def test_manifest_store_reads_and_revalidates_expected_integrity(
    tmp_path: Path,
) -> None:
    store = EvidenceManifestStore(tmp_path, max_output_bytes=64 * 1024)
    stored = store.write(USER_ID, ASSET_ID, manifest())

    loaded = store.read(
        USER_ID,
        ASSET_ID,
        stored.storage_key,
        expected_sha256=stored.sha256,
    )

    assert loaded == manifest()


def test_manifest_store_rejects_tampered_payload(tmp_path: Path) -> None:
    store = EvidenceManifestStore(tmp_path, max_output_bytes=64 * 1024)
    stored = store.write(USER_ID, ASSET_ID, manifest())
    path = store.resolve_asset_key(USER_ID, ASSET_ID, stored.storage_key)
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(EvidenceProcessingError) as error:
        store.read(
            USER_ID,
            ASSET_ID,
            stored.storage_key,
            expected_sha256=stored.sha256,
        )

    assert error.value.error_code == "evidence_manifest_integrity_failed"
