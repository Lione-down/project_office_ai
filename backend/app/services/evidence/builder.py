from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.services.evidence.contracts import (
    CsvCellLocation,
    EngineVersion,
    EvidenceItem,
    EvidenceManifest,
    EvidenceProcessingError,
    ExcelCellLocation,
    ImageOcrLocation,
    ManifestIssue,
    PdfRegionLocation,
    TextLineLocation,
    WordParagraphLocation,
)
from app.services.file_safety.parsers import ParsedDocument


EVIDENCE_ENGINE_VERSION = "1.0.0"
NARRATIVE_OCR_WARNING_THRESHOLD = 0.75
NUMERIC_OCR_BLOCK_THRESHOLD = 0.90
NUMERIC_VALUE = re.compile(
    r"^\s*([¥￥$]?)([-+]?\d[\d,]*(?:\.\d+)?)\s*(%|元|万元|亿元|人|个|件|套|台)?\s*$"
)
UNIT_MAP = {
    "%": ("PERCENT", None),
    "元": ("CNY", "CNY"),
    "万元": ("CNY_10K", "CNY"),
    "亿元": ("CNY_100M", "CNY"),
    "人": ("COUNT_PERSON", None),
    "个": ("COUNT_ITEM", None),
    "件": ("COUNT_ITEM", None),
    "套": ("COUNT_SET", None),
    "台": ("COUNT_UNIT", None),
}


@dataclass(frozen=True)
class SourceValue:
    raw_value: str
    location: Any
    ocr_confidence: float | None = None
    ocr_engine: EngineVersion | None = None


class EvidenceManifestBuilder:
    def __init__(self, ocr_client, *, max_evidence_items: int = 11_563) -> None:
        self._ocr_client = ocr_client
        self._max_evidence_items = max_evidence_items

    async def build(
        self,
        *,
        asset_id: UUID,
        asset_version: str,
        document: ParsedDocument,
        source_path: Path | None,
        mime_type: str | None,
        content_sha256: str,
    ) -> EvidenceManifest:
        try:
            return await self._build(
                asset_id=asset_id,
                asset_version=asset_version,
                document=document,
                source_path=source_path,
                mime_type=mime_type,
                content_sha256=content_sha256,
            )
        except ValidationError as exception:
            raise EvidenceProcessingError(
                "evidence_manifest_invalid", "Evidence Manifest 校验失败"
            ) from exception

    async def _build(
        self,
        *,
        asset_id: UUID,
        asset_version: str,
        document: ParsedDocument,
        source_path: Path | None,
        mime_type: str | None,
        content_sha256: str,
    ) -> EvidenceManifest:
        sources, ocr_engine = await self._sources(
            document, source_path, mime_type, content_sha256
        )
        evidence = tuple(
            self._evidence_item(
                asset_id=asset_id,
                asset_version=asset_version,
                document=document,
                source=source,
            )
            for source in sources
            if source.raw_value.strip()
        )
        warnings = tuple(
            ManifestIssue(code=code, evidence_id=item.evidence_id)
            for item in evidence
            for code in item.warnings
            if code == "ocr_narrative_low_confidence"
        )
        blockers = tuple(
            ManifestIssue(code=code, evidence_id=item.evidence_id)
            for item in evidence
            for code in item.warnings
            if code in {"ocr_numeric_low_confidence", "numeric_unit_unknown"}
        )
        manifest_digest = sha256(
            json.dumps(
                {
                    "asset_id": str(asset_id),
                    "asset_version": asset_version,
                    "evidence_ids": [item.evidence_id for item in evidence],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return EvidenceManifest(
            schema_version="evidence-manifest.v1",
            manifest_id=f"m-{manifest_digest}",
            asset_id=asset_id,
            asset_version=asset_version,
            generated_at=datetime.now(UTC),
            generator=EngineVersion(
                name="office-ai-evidence", version=EVIDENCE_ENGINE_VERSION
            ),
            source_parser=EngineVersion(
                name=document.parser_name, version=document.parser_version
            ),
            ocr_engine=ocr_engine,
            evidence=evidence,
            warnings=warnings,
            blockers=blockers,
        )

    async def _sources(
        self,
        document: ParsedDocument,
        source_path: Path | None,
        mime_type: str | None,
        content_sha256: str,
    ) -> tuple[list[SourceValue], EngineVersion | None]:
        content = document.content
        if document.kind == "pending_ocr":
            if source_path is None or mime_type is None:
                raise EvidenceProcessingError(
                    "evidence_source_invalid", "OCR 来源定位无效"
                )
            result = await self._ocr_client.recognize(
                source_path,
                mime_type=mime_type,
                content_sha256=content_sha256,
            )
            engine = EngineVersion(
                name=result.engine.name, version=result.engine.version
            )
            return self._bounded_sources(
                SourceValue(
                    raw_value=item.text,
                    location=ImageOcrLocation(kind="image_ocr", bbox=item.bbox),
                    ocr_confidence=item.confidence,
                    ocr_engine=engine,
                )
                for item in result.items
            ), engine
        if document.kind == "workbook":
            return self._bounded_sources(self._workbook_sources(content)), None
        if document.kind == "table":
            return self._bounded_sources(self._table_sources(content)), None
        if "paragraphs" in content:
            paragraph_items = content.get("paragraph_items")
            if paragraph_items is None:
                paragraph_items = [
                    {"paragraph": index, "text": value}
                    for index, value in enumerate(content["paragraphs"], start=1)
                ]
            return self._bounded_sources(
                SourceValue(
                    raw_value=item["text"],
                    location=WordParagraphLocation(
                        kind="word_paragraph", paragraph=item["paragraph"]
                    ),
                )
                for item in paragraph_items
            ), None
        if "page_blocks" in content:
            return self._bounded_sources(
                SourceValue(
                    raw_value=block["text"],
                    location=PdfRegionLocation(
                        kind="pdf_region",
                        page=block["page"],
                        bbox=tuple(block["bbox"]),
                    ),
                )
                for block in content["page_blocks"]
            ), None
        if document.kind == "text":
            return self._bounded_sources(
                SourceValue(
                    raw_value=value,
                    location=TextLineLocation(kind="text_line", line=index),
                )
                for index, value in enumerate(content["text"].splitlines(), start=1)
            ), None
        raise EvidenceProcessingError(
            "evidence_source_invalid", "解析结果缺少可追踪位置"
        )

    @staticmethod
    def _workbook_sources(content: dict[str, Any]):
        for sheet in content["sheets"]:
            cells = sheet.get("cells")
            if cells is None:
                cells = [
                    {"cell": f"{_excel_column(column)}{row}", "value": value}
                    for row, values in enumerate(sheet["rows"], start=1)
                    for column, value in enumerate(values, start=1)
                ]
            for cell in cells:
                yield SourceValue(
                    raw_value=str(cell["value"]),
                    location=ExcelCellLocation(
                        kind="excel_cell",
                        sheet=sheet["name"],
                        cell=cell["cell"],
                    ),
                )

    @staticmethod
    def _table_sources(content: dict[str, Any]):
        for row_index, row in enumerate(content["rows"], start=1):
            for column_index, value in enumerate(row, start=1):
                yield SourceValue(
                    raw_value=str(value),
                    location=CsvCellLocation(
                        kind="csv_cell", row=row_index, column=column_index
                    ),
                )

    def _bounded_sources(self, sources) -> list[SourceValue]:
        bounded = []
        for source in sources:
            if len(bounded) >= self._max_evidence_items:
                raise EvidenceProcessingError(
                    "evidence_item_limit_exceeded",
                    "Evidence Manifest 证据项超过允许上限",
                )
            bounded.append(source)
        return bounded

    @staticmethod
    def _evidence_item(
        *,
        asset_id: UUID,
        asset_version: str,
        document: ParsedDocument,
        source: SourceValue,
    ) -> EvidenceItem:
        normalized, unit, currency = _numeric_value(source.raw_value)
        value_kind = "number" if normalized is not None else "narrative"
        warnings = []
        if (
            value_kind == "narrative"
            and source.ocr_confidence is not None
            and source.ocr_confidence < NARRATIVE_OCR_WARNING_THRESHOLD
        ):
            warnings.append("ocr_narrative_low_confidence")
        if value_kind == "number":
            if (
                source.ocr_confidence is not None
                and source.ocr_confidence < NUMERIC_OCR_BLOCK_THRESHOLD
            ):
                warnings.append("ocr_numeric_low_confidence")
            if unit is None:
                warnings.append("numeric_unit_unknown")
        identity = json.dumps(
            {
                "asset_id": str(asset_id),
                "asset_version": asset_version,
                "location": source.location.model_dump(mode="json"),
                "raw_value": source.raw_value,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        evidence_id = "e-" + sha256(identity.encode("utf-8")).hexdigest()
        return EvidenceItem(
            evidence_id=evidence_id,
            evidence_type="source_fact",
            asset_id=asset_id,
            asset_version=asset_version,
            location=source.location,
            raw_value=source.raw_value,
            normalized_value=normalized,
            value_kind=value_kind,
            unit=unit,
            currency=currency,
            ocr_confidence=source.ocr_confidence,
            parser_name=document.parser_name,
            parser_version=document.parser_version,
            ocr_engine_name=source.ocr_engine.name if source.ocr_engine else None,
            ocr_engine_version=(
                source.ocr_engine.version if source.ocr_engine else None
            ),
            warnings=tuple(warnings),
            calculation_blocked=any(
                code in {"ocr_numeric_low_confidence", "numeric_unit_unknown"}
                for code in warnings
            ),
        )


def _numeric_value(value: str) -> tuple[str | None, str | None, str | None]:
    matched = NUMERIC_VALUE.fullmatch(value)
    if matched is None:
        return None, None, None
    symbol, number, suffix = matched.groups()
    try:
        normalized = format(Decimal(number.replace(",", "")), "f")
    except InvalidOperation:
        return None, None, None
    unit, currency = UNIT_MAP.get(suffix, (None, None))
    symbol_currency = None
    if symbol in {"¥", "￥"}:
        symbol_currency = "CNY"
    elif symbol == "$":
        symbol_currency = "USD"
    if symbol_currency is not None:
        if suffix and currency != symbol_currency:
            return normalized, None, None
        currency = symbol_currency
        unit = unit or symbol_currency
    return normalized, unit, currency


def _excel_column(index: int) -> str:
    letters = []
    while index:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))
