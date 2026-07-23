from hashlib import sha256
from pathlib import Path

import pytest

from app.services.quality.presentation.inspector import PresentationPackageInspector
from app.services.quality.presentation.repair import (
    PresentationDeterministicRepair,
    PresentationRepairError,
)
from tests.quality.presentation.samples import write_presentation_sample


def test_repair_fixes_geometry_and_long_title_without_overwriting_source(
    tmp_path: Path,
) -> None:
    source = write_presentation_sample(
        tmp_path / "source.pptx",
        overflow_slide=2,
        long_title_slide=3,
    )
    source_before = source.read_bytes()
    inspector = PresentationPackageInspector()
    initial = inspector.inspect(
        source,
        expected_slide_count=3,
        expected_evidence_ids={"ev-revenue"},
    )
    target = tmp_path / "repaired.pptx"

    repaired = PresentationDeterministicRepair().repair(
        source, target, initial.findings
    )
    final = inspector.inspect(
        target,
        expected_slide_count=3,
        expected_evidence_ids={"ev-revenue"},
    )

    assert source.read_bytes() == source_before
    assert repaired.path == target
    assert repaired.sha256 == sha256(target.read_bytes()).hexdigest()
    assert repaired.byte_size == target.stat().st_size
    assert {finding.code for finding in repaired.warnings} == {
        "object_bounds_repaired",
        "title_autofit_applied",
    }
    assert final.findings == ()


def test_repair_is_not_applied_to_unrepairable_failure(tmp_path: Path) -> None:
    source = write_presentation_sample(tmp_path / "source.pptx", blank_slide=2)
    findings = (
        PresentationPackageInspector()
        .inspect(
            source,
            expected_slide_count=3,
            expected_evidence_ids={"ev-revenue"},
        )
        .findings
    )
    target = tmp_path / "repaired.pptx"

    with pytest.raises(
        PresentationRepairError, match="presentation_repair_not_applicable"
    ):
        PresentationDeterministicRepair().repair(source, target, findings)

    assert not target.exists()
