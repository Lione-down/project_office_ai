from pathlib import Path
from uuid import uuid4

from httpx import ASGITransport
import pytest

from app.services.quality.presentation.server import create_libreoffice_app
from app.services.renderers.excel.libreoffice import LibreOfficeWorkbookValidator
from app.services.renderers.excel.sidecar import (
    SpreadsheetLibreOfficeClient,
    SpreadsheetLibreOfficeRunner,
    SpreadsheetRecalculationRequest,
)
from tests.renderers.spreadsheet.test_libreoffice import FakeLibreOfficeRunner
from tests.renderers.spreadsheet.test_renderer import render_sample


def build_sidecar_harness(tmp_path: Path):
    user_id = uuid4()
    asset_id = uuid4()
    request_id = uuid4()
    files_root = tmp_path / "files"
    source = (
        files_root
        / "users"
        / str(user_id)
        / "outputs"
        / str(asset_id)
        / "analysis.xlsx"
    )
    source.parent.mkdir(parents=True)
    rendered = render_sample(source)
    fake_soffice = FakeLibreOfficeRunner()
    runner = SpreadsheetLibreOfficeRunner(
        files_root,
        tmp_path / "work",
        validator_factory=lambda root: LibreOfficeWorkbookValidator(
            root,
            runner=fake_soffice,
        ),
    )
    request = SpreadsheetRecalculationRequest(
        schema_version="libreoffice-spreadsheet-request.v1",
        request_id=request_id,
        user_id=user_id,
        asset_id=asset_id,
        source_sha256=rendered.sha256,
        source_byte_size=rendered.byte_size,
        plan_sha256=rendered.plan_sha256,
        renderer_version=rendered.renderer_version,
        template_code=rendered.template_code,
        template_version=rendered.template_version,
    )
    return runner, request, rendered, fake_soffice


def test_sidecar_runner_uses_fixed_asset_key_and_preserves_original(
    tmp_path: Path,
) -> None:
    runner, request, rendered, fake_soffice = build_sidecar_harness(tmp_path)
    original_bytes = rendered.path.read_bytes()

    response = runner.recalculate(request)

    assert rendered.path.read_bytes() == original_bytes
    assert response.schema_version == "libreoffice-spreadsheet-response.v1"
    assert response.request_id == request.request_id
    assert response.source_sha256 == rendered.sha256
    assert response.plan_sha256 == rendered.plan_sha256
    assert response.validation_copy.key.startswith(
        f"spreadsheet/{request.request_id}/{rendered.sha256}/"
    )
    assert response.validation_report.key.endswith("/validation-report.json")
    assert response.formula_count == 12
    assert response.difference_count == 0
    assert len(fake_soffice.commands) == 2


@pytest.mark.asyncio
async def test_backend_client_verifies_sidecar_response_and_artifacts(
    tmp_path: Path,
) -> None:
    runner, request, rendered, _fake_soffice = build_sidecar_harness(tmp_path)
    application = create_libreoffice_app(spreadsheet_runner=runner)
    client = SpreadsheetLibreOfficeClient(
        "http://libreoffice:8081",
        tmp_path / "work",
        transport=ASGITransport(app=application),
    )

    result = await client.recalculate(
        request_id=request.request_id,
        user_id=request.user_id,
        asset_id=request.asset_id,
        source_sha256=rendered.sha256,
        source_byte_size=rendered.byte_size,
        plan_sha256=rendered.plan_sha256,
        renderer_version=rendered.renderer_version,
        template_code=rendered.template_code,
        template_version=rendered.template_version,
    )

    assert result.report.original_sha256 == rendered.sha256
    assert result.report.plan_sha256 == rendered.plan_sha256
    assert result.validation_copy.sha256 == result.report.validation_sha256
    assert result.report_artifact.path.name == "validation-report.json"


@pytest.mark.asyncio
async def test_sidecar_rejects_client_path_fields(tmp_path: Path) -> None:
    runner, request, _rendered, _fake_soffice = build_sidecar_harness(tmp_path)
    application = create_libreoffice_app(spreadsheet_runner=runner)
    transport = ASGITransport(app=application)
    payload = request.model_dump(mode="json")
    payload["source_path"] = "C:\\private\\input.xlsx"

    from httpx import AsyncClient

    async with AsyncClient(
        transport=transport,
        base_url="http://libreoffice",
    ) as client:
        response = await client.post(
            "/v1/spreadsheet/recalculate",
            json=payload,
        )

    assert response.status_code == 422


def test_libreoffice_image_includes_calc_without_exposing_new_port() -> None:
    root = Path(__file__).resolve().parents[4]
    dockerfile = (root / "backend" / "libreoffice-service" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")

    assert "libreoffice-calc" in dockerfile
    assert 'command: ["python", "-m", "app.services.quality.presentation.server"]' in (
        compose
    )
