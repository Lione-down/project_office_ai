from pathlib import Path


COMPOSE_FILE = Path(__file__).resolve().parents[3] / "docker-compose.yml"


def test_backend_compose_exposes_asset_volume_and_size_limits() -> None:
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "app-files:/app/files" in compose
    assert "OFFICE_AI_FILES_ROOT: /app/files" in compose
    assert "OFFICE_AI_MAX_FILE_BYTES:" in compose
    assert "OFFICE_AI_MAX_IMAGE_BYTES:" in compose
    assert "OFFICE_AI_MAX_TASK_BYTES:" in compose
