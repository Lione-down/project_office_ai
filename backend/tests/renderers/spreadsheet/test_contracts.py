from copy import deepcopy

import pytest

from app.services.renderers.excel.contracts import (
    WorkbookContractError,
    WorkbookPlan,
    enforce_workbook_limits,
    workbook_plan_json_schema,
    workbook_plan_sha256,
)


def valid_workbook_plan(
    template_code: str = "excel.analysis-dashboard.v1",
) -> dict:
    return {
        "schema_version": "workbook-plan.v1",
        "renderer_version": "excel-renderer.v1",
        "template": {"code": template_code, "version": "1.0.0"},
        "locale": "zh-CN",
        "metadata": {
            "title": "销售经营分析",
            "subject": "固定样本",
            "author": "Office AI",
            "company": "Office AI",
            "revision": "1",
        },
        "evidence_ids": ["ev.sales.q1", "ev.sales.q2"],
        "sheets": [
            {
                "kind": "data",
                "name": "销售明细",
                "title": "销售明细",
                "columns": [
                    {"key": "region", "header": "区域", "value_type": "text"},
                    {"key": "period", "header": "期间", "value_type": "text"},
                    {
                        "key": "previous_sales",
                        "header": "上期销售额",
                        "value_type": "number",
                    },
                    {
                        "key": "current_sales",
                        "header": "本期销售额",
                        "value_type": "number",
                    },
                ],
                "computed_columns": [
                    {
                        "key": "yoy",
                        "header": "同比",
                        "value_type": "percent",
                        "calculation": {
                            "kind": "yoy",
                            "current_column": "current_sales",
                            "previous_column": "previous_sales",
                        },
                    },
                    {
                        "key": "mom",
                        "header": "环比",
                        "value_type": "percent",
                        "calculation": {
                            "kind": "mom",
                            "current_column": "current_sales",
                            "previous_column": "previous_sales",
                        },
                    },
                    {
                        "key": "rank",
                        "header": "排名",
                        "value_type": "integer",
                        "calculation": {
                            "kind": "rank",
                            "source_column": "current_sales",
                            "order": "descending",
                        },
                    },
                ],
                "rows": [
                    {
                        "region": "华东",
                        "period": "2026-Q2",
                        "previous_sales": 100,
                        "current_sales": 120,
                    },
                    {
                        "region": "华南",
                        "period": "2026-Q2",
                        "previous_sales": 80,
                        "current_sales": 60,
                    },
                    {
                        "region": "=UNTRUSTED()",
                        "period": "2026-Q2",
                        "previous_sales": 50,
                        "current_sales": 120,
                    },
                ],
                "conditional_formats": [
                    {
                        "target_column": "yoy",
                        "kind": "cell",
                        "operator": "less_than",
                        "value": 0,
                    }
                ],
                "data_validations": [
                    {
                        "target_column": "region",
                        "values": ["华东", "华南", "=UNTRUSTED()"],
                    }
                ],
                "freeze_panes": {"row": 2, "column": 0},
                "print_settings": {
                    "orientation": "landscape",
                    "fit_width": 1,
                    "fit_height": 0,
                    "repeat_header": True,
                },
            },
            {
                "kind": "summary",
                "name": "经营看板",
                "title": "经营看板",
                "metrics": [
                    {
                        "key": "total_sales",
                        "label": "销售额合计",
                        "calculation": {
                            "kind": "sum",
                            "source_sheet": "销售明细",
                            "source_column": "current_sales",
                        },
                    },
                    {
                        "key": "average_sales",
                        "label": "平均销售额",
                        "calculation": {
                            "kind": "average",
                            "source_sheet": "销售明细",
                            "source_column": "current_sales",
                        },
                    },
                    {
                        "key": "region_count",
                        "label": "区域数",
                        "calculation": {
                            "kind": "count",
                            "source_sheet": "销售明细",
                            "source_column": "current_sales",
                        },
                    },
                ],
                "charts": [
                    {
                        "chart_type": "column",
                        "title": "区域销售额",
                        "source_sheet": "销售明细",
                        "categories_column": "region",
                        "value_columns": ["current_sales"],
                        "anchor": "D3",
                    }
                ],
                "freeze_panes": {"row": 2, "column": 0},
                "print_settings": {
                    "orientation": "landscape",
                    "fit_width": 1,
                    "fit_height": 0,
                    "repeat_header": True,
                },
            },
        ],
    }


def test_workbook_plan_exports_versioned_strict_json_schema() -> None:
    schema = workbook_plan_json_schema()

    assert schema["$id"] == "https://office-ai.local/schemas/workbook-plan.v1.json"
    assert schema["title"] == "WorkbookPlan"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == "workbook-plan.v1"


def test_workbook_plan_is_stable_and_canonical() -> None:
    first = WorkbookPlan.validate_for_renderer(valid_workbook_plan())
    second_payload = valid_workbook_plan()
    second_payload["metadata"] = dict(reversed(second_payload["metadata"].items()))
    second = WorkbookPlan.validate_for_renderer(second_payload)

    assert workbook_plan_sha256(first) == workbook_plan_sha256(second)


@pytest.mark.parametrize(
    ("mutate", "error_code"),
    [
        (
            lambda plan: plan.update({"formula": '=WEBSERVICE("https://bad")'}),
            "workbook_plan_invalid",
        ),
        (
            lambda plan: plan["sheets"][0]["columns"].append(
                {"key": "region", "header": "重复", "value_type": "text"}
            ),
            "workbook_plan_invalid",
        ),
        (
            lambda plan: plan["sheets"][1]["charts"][0].update(
                {"value_columns": ["missing"]}
            ),
            "workbook_plan_invalid",
        ),
        (
            lambda plan: plan["sheets"][0].update({"name": "../escape"}),
            "workbook_plan_invalid",
        ),
    ],
)
def test_workbook_plan_rejects_unknown_formula_duplicate_or_broken_references(
    mutate, error_code: str
) -> None:
    plan = valid_workbook_plan()
    mutate(plan)

    with pytest.raises(WorkbookContractError, match=error_code):
        WorkbookPlan.validate_for_renderer(plan)


def test_workbook_plan_rejects_duplicate_evidence_and_casefolded_sheet_names() -> None:
    plan = valid_workbook_plan()
    plan["evidence_ids"].append("ev.sales.q1")
    duplicate_sheet = deepcopy(plan["sheets"][1])
    duplicate_sheet["name"] = "销售明细"
    plan["sheets"].append(duplicate_sheet)

    with pytest.raises(WorkbookContractError, match="workbook_plan_invalid"):
        WorkbookPlan.validate_for_renderer(plan)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda plan: plan["sheets"][0]["data_validations"][0].update(
            {"values": ["x" * 256]}
        ),
        lambda plan: plan["sheets"][1]["charts"][0].update({"anchor": "XFE1"}),
        lambda plan: plan["sheets"][1]["charts"][0].update({"anchor": "A1048577"}),
    ],
)
def test_workbook_plan_rejects_excel_validation_and_anchor_overflow(mutate) -> None:
    plan = valid_workbook_plan()
    mutate(plan)

    with pytest.raises(WorkbookContractError, match="workbook_plan_invalid"):
        WorkbookPlan.validate_for_renderer(plan)


def test_workbook_plan_maps_sheet_overflow_to_specific_limit_error() -> None:
    plan = valid_workbook_plan()
    data_sheet = plan["sheets"][0]
    plan["sheets"] = [
        {**deepcopy(data_sheet), "name": f"Data {index}"} for index in range(1, 22)
    ]

    with pytest.raises(
        WorkbookContractError,
        match="workbook_sheet_limit_exceeded",
    ):
        WorkbookPlan.validate_for_renderer(plan)


def test_workbook_limits_accept_exact_boundaries() -> None:
    enforce_workbook_limits(sheet_count=20, generated_cell_count=200_000)


@pytest.mark.parametrize(
    ("sheet_count", "generated_cell_count", "error_code"),
    [
        (21, 1, "workbook_sheet_limit_exceeded"),
        (1, 200_001, "workbook_cell_limit_exceeded"),
    ],
)
def test_workbook_limits_reject_values_above_boundaries(
    sheet_count: int, generated_cell_count: int, error_code: str
) -> None:
    with pytest.raises(WorkbookContractError, match=error_code):
        enforce_workbook_limits(
            sheet_count=sheet_count,
            generated_cell_count=generated_cell_count,
        )
