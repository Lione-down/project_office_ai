from uuid import UUID

from app.services.evidence.contracts import EvidenceItem, ExcelCellLocation
from app.services.terminology.contracts import TermRule
from app.services.terminology.normalizer import (
    NORMALIZATION_RULE_VERSION,
    normalize_evidence_item,
)


ASSET_ID = UUID("019f4000-0000-7000-8000-000000000001")
LIBRARY_ID = UUID("019f4000-0000-7000-8000-000000000002")


def source_fact(raw_value: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id="e-" + "c" * 64,
        evidence_type="source_fact",
        asset_id=ASSET_ID,
        asset_version="sha256:" + "d" * 64,
        location=ExcelCellLocation(kind="excel_cell", sheet="销售", cell="B2"),
        raw_value=raw_value,
        normalized_value=None,
        value_kind="number",
        unit=None,
        currency=None,
        parser_name="openpyxl-safe",
        parser_version="1.0.0",
    )


def test_normalized_evidence_preserves_source_provenance_and_snapshot() -> None:
    original = source_fact("12500")
    rule = TermRule(
        library_id=LIBRARY_ID,
        library_version=3,
        project_id=None,
        canonical_term="销售额",
        aliases=("营收",),
        unit="CNY",
        metric_scope="含税销售额",
        priority=10,
    )

    derived = normalize_evidence_item(
        fact_key="营收",
        evidence=original,
        rules=(rule,),
        project_id=None,
    )

    assert derived.evidence_id == original.evidence_id
    assert derived.evidence_type == "source_fact"
    assert derived.asset_id == original.asset_id
    assert derived.location == original.location
    assert derived.raw_value == "12500"
    assert derived.normalized_value == "12500"
    assert derived.unit == "CNY"
    assert derived.currency == "CNY"
    assert derived.canonical_term == "销售额"
    assert derived.normalization_rule_version == NORMALIZATION_RULE_VERSION
    assert derived.term_library_id == LIBRARY_ID
    assert derived.term_library_version == 3
    assert derived.normalization_unresolved == ()


def test_unknown_evidence_unit_remains_blocked_and_traceable() -> None:
    original = source_fact("12盒")

    derived = normalize_evidence_item(
        fact_key="销量",
        evidence=original,
        rules=(),
        project_id=None,
    )

    assert derived.raw_value == "12盒"
    assert derived.normalized_value == "12"
    assert derived.unit is None
    assert derived.calculation_blocked is True
    assert "unit_unknown" in derived.warnings
    assert derived.normalization_unresolved == ("unit_unknown",)


def test_explicit_unit_conflict_is_not_overridden_by_term_rule() -> None:
    original = source_fact("$125")
    rule = TermRule(
        library_id=LIBRARY_ID,
        library_version=1,
        project_id=None,
        canonical_term="销售额",
        aliases=(),
        unit="CNY",
        metric_scope="人民币销售额",
        priority=10,
    )

    derived = normalize_evidence_item(
        fact_key="销售额",
        evidence=original,
        rules=(rule,),
        project_id=None,
    )

    assert derived.unit == "USD"
    assert derived.currency == "USD"
    assert derived.calculation_blocked is True
    assert derived.normalization_unresolved == ("unit_conflict",)


def test_term_unit_resolution_clears_the_unknown_unit_blocker() -> None:
    original = source_fact("12500").model_copy(
        update={
            "warnings": ("numeric_unit_unknown",),
            "calculation_blocked": True,
        }
    )
    rule = TermRule(
        library_id=LIBRARY_ID,
        library_version=1,
        project_id=None,
        canonical_term="销售额",
        aliases=(),
        unit="CNY",
        metric_scope="含税销售额",
        priority=10,
    )

    derived = normalize_evidence_item(
        fact_key="销售额",
        evidence=original,
        rules=(rule,),
        project_id=None,
    )

    assert derived.unit == "CNY"
    assert "numeric_unit_unknown" not in derived.warnings
    assert derived.calculation_blocked is False


def test_term_unit_resolution_preserves_independent_ocr_blocker() -> None:
    original = source_fact("12500").model_copy(
        update={
            "warnings": (
                "numeric_unit_unknown",
                "ocr_numeric_low_confidence",
            ),
            "calculation_blocked": True,
        }
    )
    rule = TermRule(
        library_id=LIBRARY_ID,
        library_version=1,
        project_id=None,
        canonical_term="销售额",
        aliases=(),
        unit="CNY",
        metric_scope="含税销售额",
        priority=10,
    )

    derived = normalize_evidence_item(
        fact_key="销售额",
        evidence=original,
        rules=(rule,),
        project_id=None,
    )

    assert "numeric_unit_unknown" not in derived.warnings
    assert "ocr_numeric_low_confidence" in derived.warnings
    assert derived.calculation_blocked is True
