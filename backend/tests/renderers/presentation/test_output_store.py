from pathlib import Path
from uuid import UUID

import pytest

from app.services.renderers.presentation.output_store import (
    PresentationOutputStore,
    PresentationOutputStoreError,
)
from app.storage.local import LocalStorageAdapter


USER_ID = UUID("019f5000-0000-7000-8000-000000000001")
ASSET_ID = UUID("019f5000-0000-7000-8000-000000000002")


def test_output_store_writes_once_and_never_overwrites(tmp_path: Path) -> None:
    source = tmp_path / "source.pptx"
    source.write_bytes(b"first-version")
    store = PresentationOutputStore(tmp_path / "files")

    stored = store.persist(USER_ID, ASSET_ID, source)

    assert stored.storage_key == (
        f"users/{USER_ID}/outputs/{ASSET_ID}/presentation.pptx"
    )
    assert stored.path.read_bytes() == b"first-version"
    assert (
        LocalStorageAdapter(tmp_path / "files")
        .resolve_asset_key(USER_ID, ASSET_ID, stored.storage_key)
        .read_bytes()
        == b"first-version"
    )

    source.write_bytes(b"changed-version")
    with pytest.raises(PresentationOutputStoreError, match="output_already_exists"):
        store.persist(USER_ID, ASSET_ID, source)

    assert stored.path.read_bytes() == b"first-version"


def test_output_store_rejects_invalid_key_and_partial_target(tmp_path: Path) -> None:
    store = PresentationOutputStore(tmp_path / "files")

    with pytest.raises(PresentationOutputStoreError, match="output_key_invalid"):
        store.resolve_key("../secret.pptx")
