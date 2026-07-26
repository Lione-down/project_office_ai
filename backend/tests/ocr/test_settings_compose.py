from pathlib import Path

import yaml

from app.settings.config import Settings


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_ocr_settings_are_internal_and_bounded(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFICE_AI_EVIDENCE_ROOT", str(tmp_path / "evidence"))
    settings = Settings()

    assert settings.paddleocr_url == "http://paddleocr:8080"
    assert settings.ocr_timeout_seconds > 0
    assert settings.max_ocr_response_bytes > 0
    assert settings.max_ocr_items > 0
    assert settings.max_evidence_manifest_bytes > 0
    assert settings.max_evidence_items == 10_000
    assert settings.evidence_root == tmp_path / "evidence"
    assert settings.ocr_retry_limit >= 1
    assert settings.ocr_retry_backoff_seconds >= 1


def test_compose_runs_pinned_offline_ocr_service_on_private_network() -> None:
    compose = yaml.safe_load(
        (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    worker = compose["services"]["worker"]
    backend = compose["services"]["backend"]
    paddleocr = compose["services"]["paddleocr"]

    assert worker["environment"]["OFFICE_AI_PADDLEOCR_URL"] == ("http://paddleocr:8080")
    assert worker["environment"]["OFFICE_AI_EVIDENCE_ROOT"] == "/app/evidence"
    assert worker["environment"]["OFFICE_AI_MAX_EVIDENCE_ITEMS"]
    assert worker["depends_on"]["paddleocr"]["condition"] == "service_healthy"
    worker_volumes = {item["target"]: item for item in worker["volumes"]}
    assert worker_volumes["/app/files"]["read_only"] is True
    assert worker_volumes["/app/evidence"]["read_only"] is False
    assert backend["environment"]["OFFICE_AI_PARSED_ROOT"] == "/app/parsed"
    assert backend["environment"]["OFFICE_AI_EVIDENCE_ROOT"] == "/app/evidence"
    assert "parsed-files:/app/parsed" in backend["volumes"]
    assert "evidence-files:/app/evidence" in backend["volumes"]

    assert paddleocr["build"]["context"] == "./backend"
    assert paddleocr["build"]["dockerfile"] == "ocr-service/Dockerfile"
    assert paddleocr["read_only"] is True
    assert paddleocr["networks"] == ["private"]
    assert paddleocr["mem_limit"]
    assert paddleocr["cpus"]
    assert paddleocr["pids_limit"]
    assert "http://127.0.0.1:8080/health" in paddleocr["healthcheck"]["test"][-1]

    dockerfile = (PROJECT_ROOT / "backend" / "ocr-service" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    assert "paddlepaddle/paddle:3.3.1" in dockerfile
    assert "paddlepaddle==3.1.1" in dockerfile
    assert "paddleocr==3.7.0" in dockerfile
    assert "HOME=/opt/paddle-home" in dockerfile
    assert "PADDLE_OCR_BASE_DIR" in dockerfile
    assert "PADDLE_PDX_CACHE_HOME" in dockerfile
    assert "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True" in dockerfile
    assert "PP-OCRv5_mobile_det" in dockerfile
    assert "PP-OCRv5_mobile_rec" in dockerfile
