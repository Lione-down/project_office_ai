import re
import unicodedata

from app.services.terminology.errors import TerminologyOperationError


_UNIT_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,31}$")


def library_fields(*, name: str, description: str | None) -> dict[str, str | None]:
    return {
        "name": normalized_text(name, "术语库名称", 128),
        "description": optional_text(description, "术语库说明", 1024),
    }


def item_fields(values: dict) -> dict:
    canonical_term = normalized_text(values.get("canonical_term"), "标准术语", 255)
    aliases = normalized_aliases(values.get("aliases", ()), canonical_term)
    unit = optional_text(values.get("unit"), "标准单位", 32)
    if unit is not None:
        unit = unit.upper()
        if _UNIT_CODE.fullmatch(unit) is None:
            raise TerminologyOperationError(
                "term_unit_invalid", "标准单位代码无效", 422
            )
    priority = values.get("priority", 0)
    if (
        isinstance(priority, bool)
        or not isinstance(priority, int)
        or not -1000 <= priority <= 1000
    ):
        raise TerminologyOperationError("term_priority_invalid", "术语优先级无效", 422)
    return {
        "canonical_term": canonical_term,
        "aliases": list(aliases),
        "unit": unit,
        "definition": optional_text(values.get("definition"), "术语定义", 2048),
        "metric_scope": optional_text(values.get("metric_scope"), "指标口径", 1024),
        "priority": priority,
    }


def normalized_text(value, label: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise TerminologyOperationError("term_field_invalid", f"{label}无效", 422)
    normalized = unicodedata.normalize("NFKC", value).strip()
    if (
        not normalized
        or len(normalized) > max_length
        or any(
            unicodedata.category(character).startswith("C") for character in normalized
        )
    ):
        raise TerminologyOperationError("term_field_invalid", f"{label}无效", 422)
    return normalized


def optional_text(value, label: str, max_length: int) -> str | None:
    if value is None:
        return None
    return normalized_text(value, label, max_length)


def normalized_aliases(values, canonical_term: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)) or len(values) > 100:
        raise TerminologyOperationError("term_aliases_invalid", "术语别名无效", 422)
    canonical_key = term_key(canonical_term)
    aliases = []
    seen = set()
    for value in values:
        alias = normalized_text(value, "术语别名", 255)
        key = term_key(alias)
        if key == canonical_key or key in seen:
            continue
        seen.add(key)
        aliases.append(alias)
    return tuple(aliases)


def term_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()
