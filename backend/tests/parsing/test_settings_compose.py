import ast
from pathlib import Path

import pytest
import yaml

from app.settings.config import Settings


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_file_processing_settings_are_bounded(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFICE_AI_PARSED_ROOT", str(tmp_path / "parsed"))
    settings = Settings()

    assert settings.parsed_root == tmp_path / "parsed"
    assert settings.clamav_host == "clamav"
    assert settings.clamav_port == 3310
    assert settings.clamav_timeout_seconds > 0
    assert settings.max_pdf_pages == 200
    assert settings.max_excel_sheets == 100
    assert settings.max_excel_non_empty_cells == 300_000
    assert settings.max_archive_uncompressed_bytes > settings.max_file_bytes
    assert settings.max_image_decoded_bytes > settings.max_image_bytes
    assert settings.max_task_files == 20
    assert (
        settings.max_office_xml_member_bytes < settings.max_archive_uncompressed_bytes
    )
    assert settings.max_parser_structural_items > settings.max_excel_non_empty_cells
    assert settings.parser_timeout_seconds > 0
    assert settings.processing_lease_seconds > settings.parser_timeout_seconds
    assert settings.max_parsed_output_bytes > 0


def test_processing_lease_must_cover_scan_and_parser_timeouts(monkeypatch) -> None:
    monkeypatch.setenv("OFFICE_AI_CLAMAV_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("OFFICE_AI_PARSER_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("OFFICE_AI_PROCESSING_LEASE_SECONDS", "60")

    with pytest.raises(ValueError, match="processing lease"):
        Settings()


def test_worker_compose_has_read_only_input_bounded_output_and_no_provider_secret() -> (
    None
):
    compose = yaml.safe_load(
        (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    worker = compose["services"]["worker"]

    assert worker["build"]["context"] == "./backend"
    assert worker["command"] == ["python", "-m", "app.workers.asset_processing"]
    assert worker["read_only"] is True
    assert worker["mem_limit"] == "768m"
    assert worker["cpus"] == 1.0
    assert worker["pids_limit"] == 128
    assert worker["networks"] == ["private"]
    assert "OFFICE_AI_MASTER_KEY" not in worker["environment"]
    assert "OFFICE_AI_PROVIDER_TIMEOUT_SECONDS" not in worker["environment"]
    assert worker["environment"]["OFFICE_AI_PARSED_ROOT"] == "/app/parsed"
    assert worker["environment"]["OFFICE_AI_MAX_PARSED_OUTPUT_BYTES"]
    assert worker["environment"]["OFFICE_AI_MAX_IMAGE_DECODED_BYTES"]
    assert worker["environment"]["OFFICE_AI_MAX_TASK_FILES"]
    assert (
        worker["environment"]["OFFICE_AI_MAX_EXCEL_SHEETS"]
        == "${OFFICE_AI_MAX_EXCEL_SHEETS:-100}"
    )
    assert worker["environment"]["OFFICE_AI_MAX_OFFICE_XML_MEMBER_BYTES"]
    assert worker["environment"]["OFFICE_AI_MAX_PARSER_STRUCTURAL_ITEMS"]
    assert worker["environment"]["OFFICE_AI_PARSER_TIMEOUT_SECONDS"]
    assert worker["environment"]["OFFICE_AI_PROCESSING_LEASE_SECONDS"]

    volumes = {item["target"]: item for item in worker["volumes"]}
    assert volumes["/app/files"]["read_only"] is True
    assert volumes["/app/parsed"]["read_only"] is False
    assert compose["networks"]["private"]["internal"] is True


def test_clamav_compose_uses_resolvable_pinned_patch_release() -> None:
    compose = yaml.safe_load(
        (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    clamav = compose["services"]["clamav"]

    assert clamav["image"] == "clamav/clamav:1.4.5"
    assert clamav["user"] == "100:101"
    assert clamav["init"] is False
    assert clamav["read_only"] is True
    assert clamav["entrypoint"] == ["/sbin/tini", "--"]
    assert clamav["command"] == ["clamd", "--foreground"]
    assert "/run/clamav:uid=100,gid=101,mode=0750" in clamav["tmpfs"]
    assert "/tmp:uid=100,gid=101,mode=0750" in clamav["tmpfs"]
    assert "/var/log/clamav:uid=100,gid=101,mode=0750" in clamav["tmpfs"]


def test_worker_module_entrypoint_is_safe_for_spawned_parser_children() -> None:
    module = ast.parse(
        (
            PROJECT_ROOT
            / "backend"
            / "app"
            / "workers"
            / "asset_processing"
            / "__main__.py"
        ).read_text(encoding="utf-8")
    )

    guards = [node for node in module.body if isinstance(node, ast.If)]
    assert any(
        isinstance(guard.test, ast.Compare)
        and isinstance(guard.test.left, ast.Name)
        and guard.test.left.id == "__name__"
        and any(
            isinstance(comparator, ast.Constant) and comparator.value == "__main__"
            for comparator in guard.test.comparators
        )
        and any(
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Name)
            and statement.value.func.id == "main"
            for statement in guard.body
        )
        for guard in guards
    )
