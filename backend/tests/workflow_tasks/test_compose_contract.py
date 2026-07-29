from pathlib import Path

import yaml


COMPOSE_FILE = Path(__file__).resolve().parents[3] / "docker-compose.yml"


def test_workflow_worker_isolated_runtime_can_consume_brief_jobs() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    services = compose["services"]
    worker = services["workflow-worker"]

    assert worker["command"] == ["python", "-m", "app.workers.workflow"]
    assert worker["user"] == "10001:10001"
    assert worker["read_only"] is True
    assert worker["networks"] == ["edge", "private"]
    assert worker["environment"]["OFFICE_AI_MASTER_KEY"] == (
        "${OFFICE_AI_MASTER_KEY:-}"
    )
    assert "OFFICE_AI_SESSION_SECRET" not in worker["environment"]
    assert {
        "source": "evidence-files",
        "target": "/app/evidence",
        "read_only": True,
        "type": "volume",
    } in worker["volumes"]
    assert {
        "source": "app-files",
        "target": "/app/files",
        "type": "volume",
    } in worker["volumes"]
    assert worker["environment"]["OFFICE_AI_MEDIA_PUBLIC_URL_INPUT_ENABLED"] == "false"
    assert worker["depends_on"]["mysql"]["condition"] == "service_healthy"
    assert worker["depends_on"]["redis"]["condition"] == "service_healthy"
    assert services["worker"]["networks"] == ["private"]
    assert "OFFICE_AI_MASTER_KEY" not in services["worker"]["environment"]


def test_generation_worker_consumes_render_jobs_without_provider_credentials() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    services = compose["services"]
    worker = services["generation-worker"]

    assert worker["command"] == ["python", "-m", "app.workers.generation"]
    assert worker["user"] == "10001:10001"
    assert worker["read_only"] is True
    assert worker["networks"] == ["private"]
    assert "OFFICE_AI_MASTER_KEY" not in worker["environment"]
    assert "OFFICE_AI_SESSION_SECRET" not in worker["environment"]
    assert {
        "source": "app-files",
        "target": "/app/files",
        "read_only": False,
        "type": "volume",
    } in worker["volumes"]
    assert {
        "source": "shared-work",
        "target": "/app/rendered",
        "read_only": True,
        "type": "volume",
    } in worker["volumes"]
    assert worker["environment"]["OFFICE_AI_EVIDENCE_ROOT"] == "/app/evidence"
    assert {
        "source": "evidence-files",
        "target": "/app/evidence",
        "read_only": True,
        "type": "volume",
    } in worker["volumes"]
    assert worker["depends_on"]["mysql"]["condition"] == "service_healthy"
    assert worker["depends_on"]["redis"]["condition"] == "service_healthy"
    assert worker["depends_on"]["ppt-renderer"]["condition"] == "service_healthy"
    assert worker["depends_on"]["libreoffice"]["condition"] == "service_healthy"
