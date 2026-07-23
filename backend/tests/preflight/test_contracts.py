from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.services.preflight.catalog import (
    EXCEL_DEFAULT_TEMPLATE,
    PPT_DEFAULT_TEMPLATE,
    TemplateSelectionError,
    build_alpha_output_plan,
)
from app.services.preflight.contracts import ConflictResolution


def test_combined_plan_uses_one_versioned_template_per_output() -> None:
    plan = build_alpha_output_plan(
        (
            "ppt.sales-business-review.v1",
            "excel.sales-analysis-dashboard.v1",
        ),
        (),
        Decimal("1.0000"),
    )

    assert [
        (item.kind, item.template_code, item.template_version) for item in plan
    ] == [
        ("pptx", PPT_DEFAULT_TEMPLATE, "1.0.0"),
        ("xlsx", EXCEL_DEFAULT_TEMPLATE, "1.0.0"),
    ]
    assert [item.estimated_credits for item in plan] == [800, 800]


def test_each_output_credit_is_rounded_up_before_combined_total() -> None:
    plan = build_alpha_output_plan(
        (
            "ppt.sales-business-review.v1",
            "excel.sales-analysis-dashboard.v1",
        ),
        (),
        Decimal("1.0001"),
    )

    assert [item.estimated_credits for item in plan] == [801, 801]
    assert sum(item.estimated_credits for item in plan) == 1602


def test_template_from_the_wrong_output_kind_is_incompatible() -> None:
    with pytest.raises(TemplateSelectionError) as error:
        build_alpha_output_plan(
            ("ppt.sales-business-review.v1",),
            ((EXCEL_DEFAULT_TEMPLATE, "1.0.0"),),
            Decimal("1.0000"),
        )

    assert error.value.error_code == "template_incompatible"


def test_resolution_action_must_match_the_blocker_type() -> None:
    with pytest.raises(ValidationError):
        ConflictResolution(
            code="unit_unknown",
            evidence_ids=(f"e-{'1' * 64}",),
            action="choose_source",
            selected_evidence_id=f"e-{'1' * 64}",
        )
