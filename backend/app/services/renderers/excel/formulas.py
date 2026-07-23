from collections.abc import Sequence

from xlsxwriter.utility import xl_col_to_name

from app.services.renderers.excel.contracts import (
    ComparisonCalculation,
    RankCalculation,
    SummaryCalculation,
)


FORMULA_FUNCTION_WHITELIST = frozenset(
    {"AVERAGE", "COUNT", "IFERROR", "RANK.EQ", "SUM"}
)


def comparison_formula(
    calculation: ComparisonCalculation,
    row_number: int,
    column_indexes: dict[str, int],
    row_values: dict[str, float | int],
) -> tuple[str, float]:
    current_column = xl_col_to_name(column_indexes[calculation.current_column])
    previous_column = xl_col_to_name(column_indexes[calculation.previous_column])
    current = float(row_values[calculation.current_column])
    previous = float(row_values[calculation.previous_column])
    cached = 0.0 if previous == 0 else (current - previous) / previous
    formula = (
        f"=IFERROR(({current_column}{row_number}-{previous_column}{row_number})"
        f"/{previous_column}{row_number},0)"
    )
    return formula, cached


def rank_formula(
    calculation: RankCalculation,
    row_number: int,
    first_row_number: int,
    last_row_number: int,
    column_indexes: dict[str, int],
    source_values: Sequence[float | int],
    row_index: int,
) -> tuple[str, int]:
    source_column = xl_col_to_name(column_indexes[calculation.source_column])
    order = 0 if calculation.order == "descending" else 1
    value = float(source_values[row_index])
    if order == 0:
        cached = 1 + sum(float(item) > value for item in source_values)
    else:
        cached = 1 + sum(float(item) < value for item in source_values)
    formula = (
        f"=RANK.EQ({source_column}{row_number},"
        f"${source_column}${first_row_number}:${source_column}${last_row_number},"
        f"{order})"
    )
    return formula, cached


def summary_formula(
    calculation: SummaryCalculation,
    source_column_index: int,
    first_row_number: int,
    last_row_number: int,
    source_values: Sequence[float | int],
) -> tuple[str, float | int]:
    function = {
        "sum": "SUM",
        "average": "AVERAGE",
        "count": "COUNT",
    }[calculation.kind]
    source_column = xl_col_to_name(source_column_index)
    quoted_sheet = _quote_sheet(calculation.source_sheet)
    formula = (
        f"={function}({quoted_sheet}!${source_column}${first_row_number}:"
        f"${source_column}${last_row_number})"
    )
    if calculation.kind == "sum":
        cached: float | int = sum(source_values)
    elif calculation.kind == "average":
        cached = sum(source_values) / len(source_values)
    else:
        cached = len(source_values)
    return formula, cached


def _quote_sheet(name: str) -> str:
    return f"'{name.replace(chr(39), chr(39) * 2)}'"
