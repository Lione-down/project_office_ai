from uuid import UUID

import pytest

from app.services.file_safety.contracts import FileSafetyError
from app.services.file_safety.output_store import ParsedOutputStore
from app.services.file_safety.parsers import ParsedDocument


USER_ID = UUID("019f0000-0000-7000-8000-000000000001")
ASSET_ID = UUID("019f0000-0000-7000-8000-000000000002")


def document(text: str) -> ParsedDocument:
    return ParsedDocument(
        schema_version="parsed-content.v1",
        parser_name="safe-text",
        parser_version="1.0",
        kind="text",
        content={"text": text, "trust": "untrusted"},
        warnings=(),
    )


def test_output_store_writes_only_to_immutable_asset_path(tmp_path) -> None:
    store = ParsedOutputStore(tmp_path, max_output_bytes=1024)

    key = store.write(USER_ID, ASSET_ID, document("hello"))
    path = store.resolve_asset_key(USER_ID, ASSET_ID, key)

    assert key == f"users/{USER_ID}/parsed/{ASSET_ID}/content.json"
    assert path.is_file()
    assert '"trust":"untrusted"' in path.read_text(encoding="utf-8")


def test_output_store_rejects_output_over_quota_without_partial_file(tmp_path) -> None:
    store = ParsedOutputStore(tmp_path, max_output_bytes=32)

    with pytest.raises(FileSafetyError) as captured:
        store.write(USER_ID, ASSET_ID, document("x" * 100))

    assert captured.value.error_code == "parsed_output_too_large"
    assert list(tmp_path.rglob("*")) == []


def test_output_store_deletes_only_the_exact_asset_output(tmp_path) -> None:
    store = ParsedOutputStore(tmp_path, max_output_bytes=1024)
    key = store.write(USER_ID, ASSET_ID, document("hello"))
    sibling_id = UUID("019f0000-0000-7000-8000-000000000003")
    sibling_key = store.write(USER_ID, sibling_id, document("keep"))

    store.delete(USER_ID, ASSET_ID, key)

    assert not store.resolve_asset_key(USER_ID, ASSET_ID, key).exists()
    assert store.resolve_asset_key(USER_ID, sibling_id, sibling_key).is_file()


@pytest.mark.parametrize(
    "key",
    [
        "../content.json",
        f"users/{USER_ID}/parsed/{ASSET_ID}/../content.json",
        f"users/{USER_ID}/parsed/019f0000-0000-7000-8000-000000000099/content.json",
    ],
)
def test_output_store_rejects_forged_keys(tmp_path, key) -> None:
    store = ParsedOutputStore(tmp_path, max_output_bytes=1024)

    with pytest.raises(FileSafetyError) as captured:
        store.resolve_asset_key(USER_ID, ASSET_ID, key)

    assert captured.value.error_code == "parsed_storage_key_invalid"
