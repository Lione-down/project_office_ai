from pathlib import Path
from uuid import uuid4

import pytest

from app.services.renderers.excel.output_store import (
    ExcelOutputStore,
    ExcelOutputStoreError,
)
from tests.renderers.spreadsheet.test_renderer import render_sample


def test_output_store_persists_owner_scoped_immutable_workbook(tmp_path: Path) -> None:
    source = tmp_path / "rendered.xlsx"
    render_sample(source)
    root = tmp_path / "assets"
    store = ExcelOutputStore(root)
    user_id = uuid4()
    asset_id = uuid4()

    stored = store.persist(user_id, asset_id, source)

    assert stored.storage_key == (f"users/{user_id}/outputs/{asset_id}/analysis.xlsx")
    assert stored.path.read_bytes() == source.read_bytes()
    assert store.inspect(user_id, asset_id) == stored

    with pytest.raises(ExcelOutputStoreError, match="output_already_exists"):
        store.persist(user_id, asset_id, source)
    assert stored.path.read_bytes() == source.read_bytes()


@pytest.mark.parametrize(
    "key",
    [
        "../analysis.xlsx",
        "users/not-a-uuid/outputs/not-a-uuid/analysis.xlsx",
        "users/00000000-0000-0000-0000-000000000001/outputs/"
        "00000000-0000-0000-0000-000000000002/other.xlsx",
    ],
)
def test_output_store_rejects_uncontrolled_keys(tmp_path: Path, key: str) -> None:
    with pytest.raises(ExcelOutputStoreError, match="output_key_invalid"):
        ExcelOutputStore(tmp_path).resolve_key(key)
