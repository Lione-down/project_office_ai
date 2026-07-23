from pathlib import Path

import yaml

from app.settings.config import Settings


ROOT = Path(__file__).resolve().parents[4]
COMPOSE_PATH = ROOT / "docker-compose.yml"
DOCKERFILE = ROOT / "backend" / "libreoffice-service" / "Dockerfile"


def test_quality_settings_are_non_secret_and_bounded() -> None:
    settings = Settings()

    assert settings.libreoffice_url == "http://libreoffice:8081"
    assert settings.libreoffice_timeout_seconds == 120
    assert settings.rendered_root == Path("/app/rendered")


def test_compose_uses_headless_private_libreoffice_sidecar() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    libreoffice = compose["services"]["libreoffice"]
    backend = compose["services"]["backend"]

    assert libreoffice["build"]["context"] == "./backend"
    assert libreoffice["build"]["dockerfile"] == "libreoffice-service/Dockerfile"
    assert libreoffice["command"] == [
        "python",
        "-m",
        "app.services.quality.presentation.server",
    ]
    assert libreoffice["read_only"] is True
    assert libreoffice["user"] == "10001:10001"
    assert libreoffice["networks"] == ["private"]
    assert "ports" not in libreoffice
    assert "app-files:/app/files:ro" in libreoffice["volumes"]
    assert "shared-work:/app/work" in libreoffice["volumes"]
    assert backend["environment"]["OFFICE_AI_LIBREOFFICE_URL"] == (
        "http://libreoffice:8081"
    )
    assert backend["depends_on"]["libreoffice"]["condition"] == "service_healthy"
    assert DOCKERFILE.is_file()
