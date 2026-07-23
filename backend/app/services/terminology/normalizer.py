from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from uuid import UUID

from app.services.terminology.contracts import (
    EvidenceFact,
    NormalizedEvidenceItem,
    NormalizedValue,
    TermResolution,
    TermRule,
    UnresolvedItem,
)


NORMALIZATION_RULE_VERSION = "terminology-normalization.v1"

_ABSOLUTE_DATE_PATTERNS = (
    re.compile(r"^\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*$"),
    re.compile(r"^\s*(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*$"),
)
_INCOMPLETE_DATE_PATTERN = re.compile(r"^\s*\d{1,2}月\d{1,2}日\s*$")
_NUMBER_PATTERN = re.compile(
    r"^\s*(?P<currency>¥|￥|\$|CNY|RMB|USD)?\s*"
    r"(?P<number>[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"\s*(?P<suffix>[^\d\s,.+-]+)?\s*$",
    re.IGNORECASE,
)
_UNIT_RULES: dict[str, tuple[Decimal, str | None, str | None]] = {
    "%": (Decimal("0.01"), "RATIO", None),
    "万": (Decimal(10_000), None, None),
    "亿": (Decimal(100_000_000), None, None),
    "元": (Decimal(1), "CNY", "CNY"),
    "万元": (Decimal(10_000), "CNY", "CNY"),
    "亿元": (Decimal(100_000_000), "CNY", "CNY"),
    "人": (Decimal(1), "COUNT_PERSON", None),
    "万人": (Decimal(10_000), "COUNT_PERSON", None),
    "个": (Decimal(1), "COUNT_ITEM", None),
    "万个": (Decimal(10_000), "COUNT_ITEM", None),
    "件": (Decimal(1), "COUNT_ITEM", None),
    "万件": (Decimal(10_000), "COUNT_ITEM", None),
    "套": (Decimal(1), "COUNT_SET", None),
    "万套": (Decimal(10_000), "COUNT_SET", None),
    "台": (Decimal(1), "COUNT_UNIT", None),
    "万台": (Decimal(10_000), "COUNT_UNIT", None),
}
_CURRENCY_SYMBOLS = {
    "¥": "CNY",
    "￥": "CNY",
    "CNY": "CNY",
    "RMB": "CNY",
    "$": "USD",
    "USD": "USD",
}


def normalize_value(raw_value: str, *, unit_hint: str | None = None) -> NormalizedValue:
    normalized = _normalize_value(raw_value)
    if unit_hint is None or normalized.value_kind != "number":
        return normalized
    canonical_hint = unit_hint.upper()
    if normalized.unit is None:
        unresolved = tuple(
            item for item in normalized.unresolved if item.code != "unit_unknown"
        )
        return normalized.model_copy(
            update={
                "unit": canonical_hint,
                "currency": (
                    canonical_hint if canonical_hint in {"CNY", "USD"} else None
                ),
                "unresolved": unresolved,
            }
        )
    if normalized.unit == canonical_hint:
        return normalized
    return normalized.model_copy(
        update={
            "unresolved": (
                *normalized.unresolved,
                UnresolvedItem(code="unit_conflict"),
            )
        }
    )


def _normalize_value(raw_value: str) -> NormalizedValue:
    raw = raw_value.strip()
    for pattern in _ABSOLUTE_DATE_PATTERNS:
        if matched := pattern.fullmatch(raw):
            try:
                normalized = date(
                    *(int(value) for value in matched.groups())
                ).isoformat()
            except ValueError:
                return _unresolved_value(raw_value, "date", "date_invalid")
            return NormalizedValue(
                raw_value=raw_value,
                normalized_value=normalized,
                value_kind="date",
                rule_version=NORMALIZATION_RULE_VERSION,
            )
    if _INCOMPLETE_DATE_PATTERN.fullmatch(raw):
        return _unresolved_value(raw_value, "date", "date_incomplete")

    matched = _NUMBER_PATTERN.fullmatch(raw)
    if matched is None:
        return NormalizedValue(
            raw_value=raw_value,
            normalized_value=raw,
            value_kind="narrative",
            rule_version=NORMALIZATION_RULE_VERSION,
        )

    try:
        number = Decimal(matched.group("number").replace(",", ""))
    except InvalidOperation:
        return NormalizedValue(
            raw_value=raw_value,
            normalized_value=None,
            value_kind="number",
            rule_version=NORMALIZATION_RULE_VERSION,
            unresolved=(UnresolvedItem(code="unit_unknown"),),
        )

    suffix = matched.group("suffix") or ""
    currency_marker = matched.group("currency")
    marker_currency = (
        _CURRENCY_SYMBOLS.get(currency_marker.upper() if currency_marker else "")
        if currency_marker
        else None
    )
    if suffix:
        rule = _UNIT_RULES.get(suffix)
        if rule is None:
            return NormalizedValue(
                raw_value=raw_value,
                normalized_value=_decimal_text(number),
                value_kind="number",
                rule_version=NORMALIZATION_RULE_VERSION,
                unresolved=(UnresolvedItem(code="unit_unknown"),),
            )
        scale, unit, suffix_currency = rule
        currency = suffix_currency
        if marker_currency is not None:
            if suffix_currency is not None and marker_currency != suffix_currency:
                return _numeric_conflict(raw_value, number * scale)
            if suffix_currency is None and unit is not None:
                return _numeric_conflict(raw_value, number * scale)
            currency = marker_currency
            unit = unit or marker_currency
        unresolved = () if unit is not None else (UnresolvedItem(code="unit_unknown"),)
        return NormalizedValue(
            raw_value=raw_value,
            normalized_value=_decimal_text(number * scale),
            value_kind="number",
            unit=unit,
            currency=currency,
            rule_version=NORMALIZATION_RULE_VERSION,
            unresolved=unresolved,
        )
    if marker_currency is not None:
        return NormalizedValue(
            raw_value=raw_value,
            normalized_value=_decimal_text(number),
            value_kind="number",
            unit=marker_currency,
            currency=marker_currency,
            rule_version=NORMALIZATION_RULE_VERSION,
        )
    return NormalizedValue(
        raw_value=raw_value,
        normalized_value=_decimal_text(number),
        value_kind="number",
        rule_version=NORMALIZATION_RULE_VERSION,
        unresolved=(UnresolvedItem(code="unit_unknown"),),
    )


def normalize_evidence_item(
    *,
    fact_key: str,
    evidence,
    rules: tuple[TermRule, ...],
    project_id: UUID | None,
) -> NormalizedEvidenceItem:
    resolution = resolve_term(fact_key, rules, project_id=project_id)
    normalized = normalize_value(evidence.raw_value, unit_hint=resolution.unit)
    unresolved = (*resolution.unresolved, *normalized.unresolved)
    unresolved_codes = tuple(dict.fromkeys(item.code for item in unresolved))
    original_blockers = {
        code
        for code in evidence.warnings
        if code in {"numeric_unit_unknown", "ocr_numeric_low_confidence"}
    }
    resolved_unknown_unit = (
        normalized.unit is not None and "unit_unknown" not in unresolved_codes
    )
    source_warnings = tuple(
        code
        for code in evidence.warnings
        if not (resolved_unknown_unit and code == "numeric_unit_unknown")
    )
    warnings = tuple(dict.fromkeys((*source_warnings, *unresolved_codes)))
    remaining_source_blocker = any(
        code in {"numeric_unit_unknown", "ocr_numeric_low_confidence"}
        for code in warnings
    )
    unclassified_source_blocker = evidence.calculation_blocked and not original_blockers
    return NormalizedEvidenceItem.model_validate(
        {
            **evidence.model_dump(mode="python"),
            "fact_key": fact_key,
            "canonical_term": resolution.canonical_term or fact_key.strip(),
            "normalized_value": normalized.normalized_value,
            "unit": normalized.unit,
            "currency": normalized.currency,
            "warnings": warnings,
            "calculation_blocked": (
                bool(unresolved_codes)
                or remaining_source_blocker
                or unclassified_source_blocker
            ),
            "normalization_rule_version": NORMALIZATION_RULE_VERSION,
            "term_library_id": resolution.library_id,
            "term_library_version": resolution.library_version,
            "normalization_unresolved": unresolved_codes,
        }
    )


def resolve_term(
    value: str, rules: tuple[TermRule, ...], *, project_id: UUID | None
) -> TermResolution:
    key = _term_key(value)
    matches = [
        rule
        for rule in rules
        if key
        in {
            _term_key(rule.canonical_term),
            *(_term_key(alias) for alias in rule.aliases),
        }
    ]
    project_matches = [
        rule
        for rule in matches
        if project_id is not None and rule.project_id == project_id
    ]
    candidates = project_matches or [
        rule for rule in matches if rule.project_id is None
    ]
    if not candidates:
        return TermResolution(
            canonical_term=None,
            unit=None,
            metric_scope=None,
            library_id=None,
            library_version=None,
        )

    highest_priority = max(rule.priority for rule in candidates)
    finalists = [rule for rule in candidates if rule.priority == highest_priority]
    canonical_terms = {_term_key(rule.canonical_term) for rule in finalists}
    if len(canonical_terms) > 1:
        return _unresolved_term(
            value,
            "term_ambiguous",
            {rule.canonical_term for rule in finalists},
        )
    units = {rule.unit for rule in finalists}
    if len(units) > 1:
        return _unresolved_term(
            value,
            "unit_conflict",
            {unit or "<unknown>" for unit in units},
        )
    metric_scopes = {rule.metric_scope for rule in finalists}
    if len(metric_scopes) > 1:
        return _unresolved_term(
            value,
            "metric_scope_conflict",
            {scope or "<unspecified>" for scope in metric_scopes},
        )
    selected = sorted(
        finalists,
        key=lambda rule: (
            -rule.library_version,
            str(rule.library_id),
            rule.canonical_term,
        ),
    )[0]
    return TermResolution(
        canonical_term=selected.canonical_term,
        unit=selected.unit,
        metric_scope=selected.metric_scope,
        library_id=selected.library_id,
        library_version=selected.library_version,
    )


def detect_source_conflicts(
    facts: tuple[EvidenceFact, ...],
) -> tuple[UnresolvedItem, ...]:
    grouped: dict[str, list[EvidenceFact]] = defaultdict(list)
    for fact in facts:
        grouped[_term_key(fact.fact_key)].append(fact)

    conflicts = []
    for fact_key in sorted(grouped):
        group = grouped[fact_key]
        candidates = {
            (fact.normalized_value, fact.unit)
            for fact in group
            if fact.normalized_value is not None
        }
        if len(candidates) <= 1:
            continue
        conflicts.append(
            UnresolvedItem(
                code="source_conflict",
                fact_key=group[0].fact_key,
                evidence_ids=tuple(fact.evidence_id for fact in group),
                candidates=tuple(
                    sorted(f"{value}|{unit or ''}" for value, unit in candidates)
                ),
                requires_authority=True,
            )
        )
    return tuple(conflicts)


def _unresolved_term(
    fact_key: str,
    code: str,
    candidates: set[str],
) -> TermResolution:
    return TermResolution(
        canonical_term=None,
        unit=None,
        metric_scope=None,
        library_id=None,
        library_version=None,
        unresolved=(
            UnresolvedItem(
                code=code,
                fact_key=fact_key,
                candidates=tuple(sorted(candidates)),
            ),
        ),
    )


def _unresolved_value(
    raw_value: str,
    value_kind: str,
    code: str,
) -> NormalizedValue:
    return NormalizedValue(
        raw_value=raw_value,
        normalized_value=None,
        value_kind=value_kind,
        rule_version=NORMALIZATION_RULE_VERSION,
        unresolved=(UnresolvedItem(code=code),),
    )


def _numeric_conflict(raw_value: str, value: Decimal) -> NormalizedValue:
    return NormalizedValue(
        raw_value=raw_value,
        normalized_value=_decimal_text(value),
        value_kind="number",
        rule_version=NORMALIZATION_RULE_VERSION,
        unresolved=(UnresolvedItem(code="currency_conflict"),),
    )


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _term_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()
