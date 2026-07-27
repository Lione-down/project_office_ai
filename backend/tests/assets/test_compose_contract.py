import json
from pathlib import Path

import yaml


COMPOSE_FILE = Path(__file__).resolve().parents[3] / "docker-compose.yml"


def test_default_host_ports_keep_frontend_and_backend_on_project_ports() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    frontend = compose["services"]["frontend"]
    backend = compose["services"]["backend"]

    assert frontend["ports"] == ["${OFFICE_AI_FRONTEND_PORT:-8888}:5173"]
    assert frontend["environment"]["VITE_API_BASE_URL"] == (
        "${OFFICE_AI_API_BASE_URL:-http://localhost:9999/api/v1}"
    )
    assert backend["ports"] == ["${OFFICE_AI_BACKEND_PORT:-9999}:8000"]
    assert backend["environment"]["OFFICE_AI_FRONTEND_ORIGIN"] == (
        "${OFFICE_AI_FRONTEND_ORIGIN:-http://localhost:8888}"
    )


def test_backend_compose_exposes_asset_volume_and_size_limits() -> None:
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "app-files:/app/files" in compose
    assert "OFFICE_AI_FILES_ROOT: /app/files" in compose
    assert "OFFICE_AI_MAX_FILE_BYTES:" in compose
    assert "OFFICE_AI_MAX_IMAGE_BYTES:" in compose
    assert "OFFICE_AI_MAX_TASK_BYTES:" in compose


def test_frontend_read_only_runtime_uses_non_bundling_vite_config_loader() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    vite_config = (COMPOSE_FILE.parent / "frontend" / "vite.config.ts").read_text(
        encoding="utf-8"
    )
    package = json.loads(
        (COMPOSE_FILE.parent / "frontend" / "package.json").read_text(encoding="utf-8")
    )
    dockerfile = (COMPOSE_FILE.parent / "frontend" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert compose["services"]["frontend"]["command"][-2:] == [
        "--configLoader",
        "runner",
    ]
    assert 'cacheDir: "/tmp/office-ai-vite-cache"' in vite_config
    assert package["scripts"]["test"].endswith("--configLoader runner")
    assert package["scripts"]["build"].endswith("vite build --configLoader runner")
    assert dockerfile.startswith("FROM node:22.22.2-alpine")
