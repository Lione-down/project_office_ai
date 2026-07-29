from pathlib import Path
import json
import re

from app.settings.config import Settings


ROOT = Path(__file__).resolve().parents[4]


def test_renderer_settings_are_non_secret_and_bounded() -> None:
    settings = Settings()

    assert settings.ppt_renderer_url == "http://ppt-renderer:3000"
    assert settings.rendered_root == Path("/app/rendered")
    assert settings.ppt_renderer_timeout_seconds == 120
    assert settings.max_presentation_request_bytes == 32 * 1024 * 1024


def test_compose_uses_the_real_isolated_renderer_image_and_read_only_handoff() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    renderer = compose.split("\n  ppt-renderer:\n", 1)[1].split("\n  mysql:\n", 1)[0]
    backend = compose.split("\n  backend:\n", 1)[1].split("\n  worker:\n", 1)[0]

    assert "build:\n      context: ./ppt-renderer\n      target: build" in renderer
    assert 'command: ["node", "dist/server.js"]' in renderer
    assert "read_only: true" in renderer
    assert "WORK_ROOT: /app/work" in renderer
    assert "PPT_RENDERER_BUILD_OUT_DIR: /tmp/ppt-renderer-dist" in renderer
    assert "OFFICE_AI_MASTER_KEY" not in renderer
    assert "OFFICE_AI_SESSION_SECRET" not in renderer
    assert re.search(
        r"source: shared-work\s+target: /app/rendered\s+read_only: true",
        backend,
    )
    assert "OFFICE_AI_PPT_RENDERER_URL: http://ppt-renderer:3000" in backend


def test_renderer_dockerfile_is_pinned_non_root_and_uses_npm_ci() -> None:
    dockerfile = (ROOT / "ppt-renderer" / "Dockerfile").read_text(encoding="utf-8")
    package = json.loads(
        (ROOT / "ppt-renderer" / "package.json").read_text(encoding="utf-8")
    )

    assert dockerfile.count("node:22.22.2-alpine") == 2
    assert "RUN npm ci" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "/tmp/ppt-renderer-dist" in dockerfile
    assert package["engines"]["node"] == ">=22.22.2 <25"
    assert package["scripts"]["build"] == "node scripts/build.mjs"
    assert package["scripts"]["test"].endswith("--configLoader runner")
