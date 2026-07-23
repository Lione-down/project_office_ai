from pathlib import Path

import pytest

from app.services.quality.presentation.inspector import PresentationPackageInspector
from tests.quality.presentation.samples import write_presentation_sample


@pytest.mark.parametrize(
    ("sample_name", "options", "expected_code", "expected_slide"),
    [
        ("blank.pptx", {"blank_slide": 2}, "blank_slide", 2),
        ("missing-slide.pptx", {"slide_count": 2}, "slide_missing", None),
        ("overflow.pptx", {"overflow_slide": 2}, "object_out_of_bounds", 2),
        ("missing-image.pptx", {"missing_image_slide": 2}, "image_missing", 2),
        ("long-title.pptx", {"long_title_slide": 2}, "title_overflow_risk", 2),
        ("bad-chart.pptx", {"bad_chart_slide": 2}, "chart_reference_invalid", 2),
        (
            "missing-evidence.pptx",
            {"evidence_ids": ("ev-other",)},
            "evidence_reference_missing",
            None,
        ),
    ],
)
def test_inspector_blocks_synthetic_failure_samples(
    tmp_path: Path,
    sample_name: str,
    options: dict,
    expected_code: str,
    expected_slide: int | None,
) -> None:
    sample = write_presentation_sample(tmp_path / sample_name, **options)

    result = PresentationPackageInspector().inspect(
        sample,
        expected_slide_count=3,
        expected_evidence_ids={"ev-revenue"},
    )

    finding = next(item for item in result.findings if item.code == expected_code)
    assert finding.severity == "blocker"
    assert finding.slide_number == expected_slide
    assert not hasattr(finding, "text")
    assert not hasattr(finding, "path")


def test_inspector_blocks_corrupt_ooxml(tmp_path: Path) -> None:
    sample = tmp_path / "corrupt.pptx"
    sample.write_bytes(b"not-an-ooxml-package")

    result = PresentationPackageInspector().inspect(
        sample,
        expected_slide_count=3,
        expected_evidence_ids={"ev-revenue"},
    )

    assert [finding.code for finding in result.findings] == ["ooxml_corrupt"]


def test_inspector_allows_valid_synthetic_sample(tmp_path: Path) -> None:
    sample = write_presentation_sample(tmp_path / "valid.pptx")

    result = PresentationPackageInspector().inspect(
        sample,
        expected_slide_count=3,
        expected_evidence_ids={"ev-revenue"},
    )

    assert result.slide_count == 3
    assert result.findings == ()
