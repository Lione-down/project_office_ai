from pathlib import Path
import re

from app.settings.config import Settings


ROOT = Path(__file__).resolve().parents[4]


def test_renderer_settings_are_non_secret_and_bounded() -> None:
    settings = Settings()

    assert settings.ppt_renderer_url == "http://ppt-renderer:3000"
    assert settings.rendered_root == Path("/app/rendered")
    assert settings.ppt_renderer_timeout_seconds == 120
    assert settings.max_presentation_request_bytes == 10 * 1024 * 1024


def test_compose_uses_the_real_isolated_renderer_image_and_read_only_handoff() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    renderer = compose.split("\n  ppt-renderer:\n", 1)[1].split("\n  mysql:\n", 1)[0]
    backend = compose.split("\n  backend:\n", 1)[1].split("\n  worker:\n", 1)[0]

    assert "build:\n      context: ./ppt-renderer" in renderer
    assert 'command: ["node", "dist/server.js"]' in renderer
    assert "read_only: true" in renderer
    assert "WORK_ROOT: /app/work" in renderer
    assert "OFFICE_AI_MASTER_KEY" not in renderer
    assert "OFFICE_AI_SESSION_SECRET" not in renderer
    assert re.search(
        r"source: shared-work\s+target: /app/rendered\s+read_only: true",
        backend,
    )
    assert "OFFICE_AI_PPT_RENDERER_URL: http://ppt-renderer:3000" in backend


def test_renderer_dockerfile_is_pinned_non_root_and_uses_npm_ci() -> None:
    dockerfile = (ROOT / "ppt-renderer" / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.count("node:22.17.0-alpine") == 2
    assert "RUN npm ci" in dockerfile
    assert "USER 10001:10001" in dockerfile
