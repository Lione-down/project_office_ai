import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.services.evidence.builder import EvidenceManifestBuilder
from app.services.evidence.contracts import EvidenceManifest
from app.services.evidence.contracts import EvidenceProcessingError
from app.services.evidence.store import EvidenceManifestStore
from app.services.file_safety.parsers import ParsedDocument
from app.services.ocr.contracts import OcrEngine, OcrItem, OcrResult


ASSET_ID = UUID("019f0000-0000-7000-8000-000000000021")
USER_ID = UUID("019f0000-0000-7000-8000-000000000022")
ASSET_VERSION = "sha256:" + ("a" * 64)


class StubOcrClient:
    def __init__(self, items: tuple[OcrItem, ...]) -> None:
        self.items = items
        self.calls = 0

    async def recognize(self, *_args, **_kwargs) -> OcrResult:
        self.calls += 1
        return OcrResult(
            schema_version="paddleocr-response.v1",
            engine=OcrEngine(name="PaddleOCR", version="3.7.0"),
            items=self.items,
        )


def document(*, kind: str, content: dict) -> ParsedDocument:
    return ParsedDocument(
        schema_version="parsed-content.v1",
        parser_name=f"safe-{kind}",
        parser_version="1.0.0",
        kind=kind,
        content={**content, "trust": "untrusted"},
        warnings=(),
    )


async def test_manifest_maps_excel_pdf_word_and_image_locations(
    tmp_path: Path,
) -> None:
    builder = EvidenceManifestBuilder(
        StubOcrClient(
            (
                OcrItem(
                    text="经营情况稳定",
                    confidence=0.98,
                    polygon=((1, 2), (10, 2), (10, 8), (1, 8)),
                ),
            )
        )
    )
    cases = [
        (
            document(
                kind="workbook",
                content={
                    "sheets": [
                        {
                            "name": "经营表",
                            "rows": [["100 万元"]],
                            "cells": [{"cell": "C7", "value": "100 万元"}],
                        }
                    ]
                },
            ),
            None,
            "excel_cell",
            {"sheet": "经营表", "cell": "C7"},
        ),
        (
            document(
                kind="document",
                content={
                    "pages": ["经营情况稳定"],
                    "page_blocks": [
                        {
                            "page": 2,
                            "text": "经营情况稳定",
                            "bbox": [10, 20, 100, 40],
                        }
                    ],
                },
            ),
            None,
            "pdf_region",
            {"page": 2, "bbox": (10.0, 20.0, 100.0, 40.0)},
        ),
        (
            document(
                kind="document",
                content={"paragraphs": ["经营情况稳定"]},
            ),
            None,
            "word_paragraph",
            {"paragraph": 1},
        ),
        (
            document(
                kind="pending_ocr",
                content={"status": "pending_ocr"},
            ),
            tmp_path / "chart.png",
            "image_ocr",
            {"bbox": (1.0, 2.0, 10.0, 8.0)},
        ),
    ]
    (tmp_path / "chart.png").write_bytes(b"image")

    for parsed, source_path, location_kind, expected in cases:
        manifest = await builder.build(
            asset_id=ASSET_ID,
            asset_version=ASSET_VERSION,
            document=parsed,
            source_path=source_path,
            mime_type="image/png" if source_path else None,
            content_sha256="a" * 64,
        )
        item = manifest.evidence[0]
        assert item.evidence_type == "source_fact"
        assert item.asset_id == ASSET_ID
        assert item.asset_version == ASSET_VERSION
        assert item.location.kind == location_kind
        for name, value in expected.items():
            assert getattr(item.location, name) == value


async def test_ocr_confidence_and_unknown_unit_rules_are_fail_closed(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "chart.png"
    image_path.write_bytes(b"image")
    builder = EvidenceManifestBuilder(
        StubOcrClient(
            (
                OcrItem(
                    text="经营情况稳定",
                    confidence=0.74,
                    polygon=((0, 0), (10, 0), (10, 5), (0, 5)),
                ),
                OcrItem(
                    text="123 万元",
                    confidence=0.89,
                    polygon=((0, 6), (10, 6), (10, 11), (0, 11)),
                ),
                OcrItem(
                    text="456",
                    confidence=0.99,
                    polygon=((0, 12), (10, 12), (10, 17), (0, 17)),
                ),
            )
        )
    )

    manifest = await builder.build(
        asset_id=ASSET_ID,
        asset_version=ASSET_VERSION,
        document=document(kind="pending_ocr", content={"status": "pending_ocr"}),
        source_path=image_path,
        mime_type="image/png",
        content_sha256="a" * 64,
    )

    assert {warning.code for warning in manifest.warnings} == {
        "ocr_narrative_low_confidence"
    }
    assert {blocker.code for blocker in manifest.blockers} == {
        "ocr_numeric_low_confidence",
        "numeric_unit_unknown",
    }
    numeric = manifest.evidence[1]
    assert numeric.normalized_value == "123"
    assert numeric.unit == "CNY_10K"
    assert numeric.calculation_blocked is True
    unknown_unit = manifest.evidence[2]
    assert unknown_unit.normalized_value == "456"
    assert unknown_unit.unit is None
    assert unknown_unit.calculation_blocked is True


def test_manifest_schema_rejects_ai_inference_without_provenance() -> None:
    payload = {
        "schema_version": "evidence-manifest.v1",
        "manifest_id": "m-" + ("a" * 64),
        "asset_id": str(ASSET_ID),
        "asset_version": ASSET_VERSION,
        "generated_at": "2026-07-23T00:00:00Z",
        "generator": {"name": "office-ai-evidence", "version": "1.0.0"},
        "source_parser": {"name": "safe-text", "version": "1.0.0"},
        "evidence": [
            {
                "evidence_id": "e-" + ("b" * 64),
                "evidence_type": "ai_inference",
                "asset_id": str(ASSET_ID),
                "asset_version": ASSET_VERSION,
                "location": {"kind": "text_line", "line": 1},
                "raw_value": "推断",
                "normalized_value": None,
                "value_kind": "narrative",
                "unit": None,
                "currency": None,
                "ocr_confidence": None,
                "parser_name": "safe-text",
                "parser_version": "1.0.0",
                "ocr_engine_name": None,
                "ocr_engine_version": None,
                "warnings": [],
                "calculation_blocked": False,
            }
        ],
        "warnings": [],
        "blockers": [],
    }

    with pytest.raises(ValidationError):
        EvidenceManifest.model_validate(payload)


async def test_builder_reports_schema_failure_without_partial_manifest() -> None:
    builder = EvidenceManifestBuilder(StubOcrClient(()))

    with pytest.raises(EvidenceProcessingError) as captured:
        await builder.build(
            asset_id=ASSET_ID,
            asset_version=ASSET_VERSION,
            document=document(kind="text", content={"text": "x" * 16_385}),
            source_path=None,
            mime_type=None,
            content_sha256="a" * 64,
        )

    assert captured.value.error_code == "evidence_manifest_invalid"
    assert str(captured.value) == "Evidence Manifest 校验失败"


async def test_builder_rejects_source_expansion_before_manifest_allocation() -> None:
    builder = EvidenceManifestBuilder(StubOcrClient(()), max_evidence_items=2)

    with pytest.raises(EvidenceProcessingError) as captured:
        await builder.build(
            asset_id=ASSET_ID,
            asset_version=ASSET_VERSION,
            document=document(
                kind="table",
                content={"rows": [["a", "b", "c"]]},
            ),
            source_path=None,
            mime_type=None,
            content_sha256="a" * 64,
        )

    assert captured.value.error_code == "evidence_item_limit_exceeded"


async def test_default_builder_accepts_golden_workbook_source_count() -> None:
    builder = EvidenceManifestBuilder(StubOcrClient(()))

    manifest = await builder.build(
        asset_id=ASSET_ID,
        asset_version=ASSET_VERSION,
        document=document(
            kind="table",
            content={"rows": [["x"] * 11_563]},
        ),
        source_path=None,
        mime_type=None,
        content_sha256="a" * 64,
    )

    assert len(manifest.evidence) == 11_563


async def test_default_builder_rejects_above_golden_workbook_source_count() -> None:
    builder = EvidenceManifestBuilder(StubOcrClient(()))

    with pytest.raises(EvidenceProcessingError) as captured:
        await builder.build(
            asset_id=ASSET_ID,
            asset_version=ASSET_VERSION,
            document=document(
                kind="table",
                content={"rows": [["x"] * 11_564]},
            ),
            source_path=None,
            mime_type=None,
            content_sha256="a" * 64,
        )

    assert captured.value.error_code == "evidence_item_limit_exceeded"


async def test_conflicting_currency_markers_fail_closed_as_unknown_unit() -> None:
    builder = EvidenceManifestBuilder(StubOcrClient(()))

    manifest = await builder.build(
        asset_id=ASSET_ID,
        asset_version=ASSET_VERSION,
        document=document(kind="text", content={"text": "$100 万元"}),
        source_path=None,
        mime_type=None,
        content_sha256="a" * 64,
    )

    item = manifest.evidence[0]
    assert item.normalized_value == "100"
    assert item.unit is None
    assert item.currency is None
    assert item.calculation_blocked is True
    assert {blocker.code for blocker in manifest.blockers} == {"numeric_unit_unknown"}


async def test_manifest_store_is_deterministic_atomic_and_schema_backed(
    tmp_path: Path,
) -> None:
    builder = EvidenceManifestBuilder(StubOcrClient(()))
    manifest = await builder.build(
        asset_id=ASSET_ID,
        asset_version=ASSET_VERSION,
        document=document(kind="text", content={"text": "经营情况稳定"}),
        source_path=None,
        mime_type=None,
        content_sha256="a" * 64,
    )
    store = EvidenceManifestStore(tmp_path, max_output_bytes=64 * 1024)

    stored = store.write(USER_ID, ASSET_ID, manifest)
    path = store.resolve_asset_key(USER_ID, ASSET_ID, stored.storage_key)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert stored.storage_key == (
        f"users/{USER_ID}/assets/{ASSET_ID}/extracted/evidence-manifest.json"
    )
    assert stored.sha256
    assert payload == manifest.model_dump(mode="json")
    assert not list(path.parent.glob(".*.tmp"))

    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "app"
            / "services"
            / "evidence"
            / "evidence-manifest.v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert schema == EvidenceManifest.model_json_schema()
