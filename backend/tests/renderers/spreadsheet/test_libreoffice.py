from json import loads
from pathlib import Path
import shutil
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.services.renderers.excel.libreoffice import (
    LibreOfficeWorkbookValidator,
    WorkbookValidationError,
)
from tests.renderers.spreadsheet.test_renderer import render_sample


class FakeLibreOfficeRunner:
    def __init__(
        self,
        *,
        mutate_formula: bool = False,
        mutate_original: Path | None = None,
        invalid_output: bool = False,
    ) -> None:
        self.mutate_formula = mutate_formula
        self.mutate_original = mutate_original
        self.invalid_output = invalid_output
        self.commands: list[list[str]] = []

    def __call__(self, command, **_kwargs):
        self.commands.append(list(command))
        if "--version" in command:
            return SimpleNamespace(stdout="LibreOffice 25.2.3\n", stderr="")
        output_directory = Path(command[command.index("--outdir") + 1])
        source = Path(command[-1])
        target = output_directory / source.name
        shutil.copyfile(source, target)
        if self.invalid_output:
            target.write_bytes(b"not-an-xlsx")
        if self.mutate_formula:
            replacement = target.with_suffix(".replacement.xlsx")
            with (
                ZipFile(target) as source_archive,
                ZipFile(replacement, "w", ZIP_DEFLATED) as target_archive,
            ):
                for item in source_archive.infolist():
                    payload = source_archive.read(item.filename)
                    if item.filename == "xl/worksheets/sheet2.xml":
                        payload = payload.replace(
                            b"<f>SUM('",
                            b"<f>SUM(1,2)+N('",
                            1,
                        )
                    target_archive.writestr(item, payload)
            replacement.replace(target)
        if self.mutate_original is not None:
            self.mutate_original.write_bytes(b"tampered")
        return SimpleNamespace(stdout="", stderr="")


def test_validator_recalculates_only_copy_and_writes_traceable_report(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original.xlsx"
    rendered = render_sample(original)
    runner = FakeLibreOfficeRunner()
    validator = LibreOfficeWorkbookValidator(
        tmp_path / "validation",
        runner=runner,
        soffice_executable="soffice",
    )
    original_bytes = original.read_bytes()

    result = validator.validate(rendered)

    assert original.read_bytes() == original_bytes
    assert result.validation_copy_path != original
    assert result.validation_copy_path.read_bytes() == original_bytes
    assert result.report.schema_version == "workbook-validation-report.v1"
    assert result.report.original_sha256 == rendered.sha256
    assert result.report.plan_sha256 == rendered.plan_sha256
    assert result.report.renderer_version == "excel-renderer.v1"
    assert result.report.template_code == "excel.analysis-dashboard.v1"
    assert result.report.template_version == "1.0.0"
    assert result.report.libreoffice_version == "LibreOffice 25.2.3"
    assert result.report.formula_count == 12
    assert result.report.difference_count == 0
    assert result.report.differences == ()
    assert loads(result.report_path.read_text(encoding="utf-8")) == (
        result.report.model_dump(mode="json")
    )
    assert runner.commands[0][-1] == "--version"
    assert "--headless" in runner.commands[1]
    assert any(
        item.startswith("-env:UserInstallation=file:///") for item in runner.commands[1]
    )


def test_validator_reports_formula_and_cache_difference_without_formula_text(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original.xlsx"
    rendered = render_sample(original)
    validator = LibreOfficeWorkbookValidator(
        tmp_path / "validation",
        runner=FakeLibreOfficeRunner(mutate_formula=True),
    )

    result = validator.validate(rendered)

    assert result.report.difference_count == 1
    difference = result.report.differences[0]
    assert difference.sheet_name == "经营看板"
    assert difference.cell_reference == "B3"
    assert difference.formula_changed is True
    assert difference.original_cached_value == 300
    assert difference.recalculated_cached_value == 300
    report_text = result.report_path.read_text(encoding="utf-8")
    assert "=SUM(" not in report_text


def test_validator_fails_closed_if_original_changes_during_validation(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original.xlsx"
    rendered = render_sample(original)
    validator = LibreOfficeWorkbookValidator(
        tmp_path / "validation",
        runner=FakeLibreOfficeRunner(mutate_original=original),
    )

    with pytest.raises(
        WorkbookValidationError,
        match="workbook_original_integrity_failed",
    ):
        validator.validate(rendered)


def test_validator_maps_missing_libreoffice_to_stable_error(tmp_path: Path) -> None:
    original = tmp_path / "original.xlsx"
    rendered = render_sample(original)
    validator = LibreOfficeWorkbookValidator(
        tmp_path / "validation",
        soffice_executable="definitely-missing-soffice",
    )

    with pytest.raises(
        WorkbookValidationError,
        match="libreoffice_unavailable",
    ):
        validator.validate(rendered)


def test_validator_replays_completed_artifacts_without_second_conversion(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original.xlsx"
    rendered = render_sample(original)
    runner = FakeLibreOfficeRunner()
    validator = LibreOfficeWorkbookValidator(
        tmp_path / "validation",
        runner=runner,
    )
    first = validator.validate(rendered)

    replay = validator.validate(rendered)

    assert replay == first
    assert len(runner.commands) == 2


def test_validator_replay_rejects_tampered_validation_copy(tmp_path: Path) -> None:
    original = tmp_path / "original.xlsx"
    rendered = render_sample(original)
    runner = FakeLibreOfficeRunner()
    validator = LibreOfficeWorkbookValidator(
        tmp_path / "validation",
        runner=runner,
    )
    first = validator.validate(rendered)
    first.validation_copy_path.write_bytes(b"tampered")

    with pytest.raises(
        WorkbookValidationError,
        match="workbook_validation_integrity_failed",
    ):
        validator.validate(rendered)


def test_validator_maps_invalid_recalculated_xlsx_to_stable_error(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original.xlsx"
    rendered = render_sample(original)
    validator = LibreOfficeWorkbookValidator(
        tmp_path / "validation",
        runner=FakeLibreOfficeRunner(invalid_output=True),
    )

    with pytest.raises(
        WorkbookValidationError,
        match="workbook_formula_snapshot_invalid",
    ):
        validator.validate(rendered)
