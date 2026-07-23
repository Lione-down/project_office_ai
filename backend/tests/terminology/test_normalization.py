from uuid import UUID

from app.services.terminology.contracts import EvidenceFact, TermRule
from app.services.terminology.normalizer import (
    NORMALIZATION_RULE_VERSION,
    detect_source_conflicts,
    normalize_value,
    resolve_term,
)


GLOBAL_LIBRARY_ID = UUID("019f1000-0000-7000-8000-000000000001")
PROJECT_LIBRARY_ID = UUID("019f1000-0000-7000-8000-000000000002")
PROJECT_ID = UUID("019f1000-0000-7000-8000-000000000003")


def test_currency_and_sales_units_normalize_to_base_units() -> None:
    cny = normalize_value("￥1.25万元")
    usd = normalize_value("$2,500")
    count = normalize_value("3万件")

    assert cny.normalized_value == "12500"
    assert cny.unit == "CNY"
    assert cny.currency == "CNY"
    assert usd.normalized_value == "2500"
    assert usd.unit == "USD"
    assert usd.currency == "USD"
    assert count.normalized_value == "30000"
    assert count.unit == "COUNT_ITEM"
    assert cny.rule_version == NORMALIZATION_RULE_VERSION


def test_percentage_normalizes_to_ratio() -> None:
    result = normalize_value("12.5%")

    assert result.normalized_value == "0.125"
    assert result.unit == "RATIO"
    assert result.unresolved == ()


def test_scale_only_sales_unit_uses_explicit_term_unit_hint() -> None:
    result = normalize_value("1.2万", unit_hint="CNY")

    assert result.normalized_value == "12000"
    assert result.unit == "CNY"
    assert result.currency == "CNY"
    assert result.unresolved == ()


def test_absolute_dates_normalize_without_locale_guessing() -> None:
    chinese = normalize_value("2026年7月3日")
    slashed = normalize_value("2026/07/03")

    assert chinese.normalized_value == "2026-07-03"
    assert chinese.value_kind == "date"
    assert slashed.normalized_value == chinese.normalized_value


def test_incomplete_date_is_unresolved_and_keeps_raw_value() -> None:
    result = normalize_value("7月3日")

    assert result.normalized_value is None
    assert result.raw_value == "7月3日"
    assert [item.code for item in result.unresolved] == ["date_incomplete"]


def test_unknown_unit_is_unresolved_instead_of_guessed() -> None:
    result = normalize_value("12盒")

    assert result.normalized_value == "12"
    assert result.unit is None
    assert [item.code for item in result.unresolved] == ["unit_unknown"]


def test_project_rule_overrides_global_alias_for_same_user() -> None:
    rules = (
        TermRule(
            library_id=GLOBAL_LIBRARY_ID,
            library_version=2,
            project_id=None,
            canonical_term="销售额",
            aliases=("营收",),
            unit="CNY",
            metric_scope="含税销售额",
            priority=10,
        ),
        TermRule(
            library_id=PROJECT_LIBRARY_ID,
            library_version=1,
            project_id=PROJECT_ID,
            canonical_term="净销售额",
            aliases=("营收",),
            unit="CNY",
            metric_scope="扣除退款后的销售额",
            priority=1,
        ),
    )

    resolved = resolve_term("营收", rules, project_id=PROJECT_ID)

    assert resolved.canonical_term == "净销售额"
    assert resolved.library_id == PROJECT_LIBRARY_ID
    assert resolved.unresolved == ()


def test_equal_priority_alias_collision_is_unresolved() -> None:
    rules = (
        TermRule(
            library_id=GLOBAL_LIBRARY_ID,
            library_version=1,
            project_id=None,
            canonical_term="销售额",
            aliases=("营收",),
            unit="CNY",
            metric_scope="含税",
            priority=10,
        ),
        TermRule(
            library_id=PROJECT_LIBRARY_ID,
            library_version=1,
            project_id=None,
            canonical_term="净收入",
            aliases=("营收",),
            unit="CNY",
            metric_scope="扣除退款",
            priority=10,
        ),
    )

    resolved = resolve_term("营收", rules, project_id=None)

    assert resolved.canonical_term is None
    assert [item.code for item in resolved.unresolved] == ["term_ambiguous"]


def test_equal_priority_same_term_with_different_units_is_unresolved() -> None:
    rules = (
        TermRule(
            library_id=GLOBAL_LIBRARY_ID,
            library_version=1,
            project_id=None,
            canonical_term="销售额",
            aliases=("营收",),
            unit="CNY",
            metric_scope="含税销售额",
            priority=10,
        ),
        TermRule(
            library_id=PROJECT_LIBRARY_ID,
            library_version=1,
            project_id=None,
            canonical_term="销售额",
            aliases=("营收",),
            unit="USD",
            metric_scope="含税销售额",
            priority=10,
        ),
    )

    resolved = resolve_term("营收", rules, project_id=None)

    assert resolved.canonical_term is None
    assert [item.code for item in resolved.unresolved] == ["unit_conflict"]


def test_equal_priority_same_term_with_different_scopes_is_unresolved() -> None:
    rules = (
        TermRule(
            library_id=GLOBAL_LIBRARY_ID,
            library_version=1,
            project_id=None,
            canonical_term="销售额",
            aliases=("营收",),
            unit="CNY",
            metric_scope="含税销售额",
            priority=10,
        ),
        TermRule(
            library_id=PROJECT_LIBRARY_ID,
            library_version=1,
            project_id=None,
            canonical_term="销售额",
            aliases=("营收",),
            unit="CNY",
            metric_scope="不含税销售额",
            priority=10,
        ),
    )

    resolved = resolve_term("营收", rules, project_id=None)

    assert resolved.canonical_term is None
    assert [item.code for item in resolved.unresolved] == ["metric_scope_conflict"]


def test_source_conflicts_require_authoritative_evidence() -> None:
    conflicts = detect_source_conflicts(
        (
            EvidenceFact(
                fact_key="销售额",
                evidence_id="e-" + "a" * 64,
                normalized_value="12000",
                unit="CNY",
            ),
            EvidenceFact(
                fact_key="销售额",
                evidence_id="e-" + "b" * 64,
                normalized_value="12500",
                unit="CNY",
            ),
        )
    )

    assert len(conflicts) == 1
    assert conflicts[0].code == "source_conflict"
    assert conflicts[0].requires_authority is True
    assert conflicts[0].evidence_ids == ("e-" + "a" * 64, "e-" + "b" * 64)


def test_equal_normalized_sources_do_not_conflict() -> None:
    conflicts = detect_source_conflicts(
        (
            EvidenceFact(
                fact_key="销售额",
                evidence_id="e-" + "a" * 64,
                normalized_value="12000",
                unit="CNY",
            ),
            EvidenceFact(
                fact_key="销售额",
                evidence_id="e-" + "b" * 64,
                normalized_value="12000",
                unit="CNY",
            ),
        )
    )

    assert conflicts == ()
