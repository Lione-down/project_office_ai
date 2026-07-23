import pytest

from app.skills.catalog import (
    ALPHA_SKILLS,
    SkillSelectionError,
    resolve_alpha_skill_selection,
)


def test_alpha_catalog_contains_only_the_two_versioned_user_skills() -> None:
    assert tuple(skill.skill_code for skill in ALPHA_SKILLS) == (
        "ppt.sales-business-review.v1",
        "excel.sales-analysis-dashboard.v1",
    )
    assert all(skill.version == "1.0.0" for skill in ALPHA_SKILLS)
    assert all(skill.kind == "user_workflow" for skill in ALPHA_SKILLS)
    assert all(skill.status == "published" for skill in ALPHA_SKILLS)


@pytest.mark.parametrize(
    ("skill_codes", "module"),
    [
        (("ppt.sales-business-review.v1",), "ppt"),
        (("excel.sales-analysis-dashboard.v1",), "excel"),
        (
            (
                "ppt.sales-business-review.v1",
                "excel.sales-analysis-dashboard.v1",
            ),
            "combined",
        ),
    ],
)
def test_alpha_catalog_resolves_only_known_single_or_combined_selection(
    skill_codes: tuple[str, ...], module: str
) -> None:
    selection = resolve_alpha_skill_selection(skill_codes)

    assert selection.module == module
    assert tuple(skill.skill_code for skill in selection.skills) == skill_codes


@pytest.mark.parametrize(
    "skill_codes",
    [
        (),
        ("ppt.sales-business-review.v1", "ppt.sales-business-review.v1"),
        ("unknown.skill.v1",),
        (
            "ppt.sales-business-review.v1",
            "excel.sales-analysis-dashboard.v1",
            "unknown.skill.v1",
        ),
    ],
)
def test_alpha_catalog_rejects_unknown_duplicate_or_unsupported_selection(
    skill_codes: tuple[str, ...],
) -> None:
    with pytest.raises(SkillSelectionError) as error:
        resolve_alpha_skill_selection(skill_codes)

    assert error.value.error_code == "skill_selection_invalid"
