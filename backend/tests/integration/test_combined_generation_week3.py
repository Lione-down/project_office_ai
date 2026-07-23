from uuid import UUID

from httpx import ASGITransport, AsyncClient

from app.core.application import AuthServices, create_app
from app.models.file_assets import FileAsset
from app.models.generation_tasks import GenerationTask
from app.services.generation_contracts import GenerationServices
from app.services.generation_worker import (
    ControlledStepExecutor,
    GenerationWorkerService,
    StepExecutionResult,
)
from app.settings.config import Settings
from tests.generation.conftest import BRIEF_ID


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


class Sessions:
    async def authenticate_access(self, access_token: str):
        return object()


class AllowAllCredentialLimiter:
    async def acquire(self, **_kwargs) -> bool:
        return True


async def test_confirmed_combined_brief_exposes_independent_output_quality(
    generation_harness,
) -> None:
    await generation_harness.set_combined()
    app = create_app(
        settings=Settings(),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=Sessions()),
        generation_services=GenerationServices(generation_harness.service),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/generations",
            headers={
                "Authorization": "Bearer access-token",
                "Idempotency-Key": "week3-combined-001",
            },
            json={"brief_id": str(BRIEF_ID)},
        )
        task_id = UUID(created.json()["task_id"])
        await GenerationWorkerService(
            generation_harness.session_factory,
            AllowAllCredentialLimiter(),
        ).process(
            task_id,
            ControlledStepExecutor(
                [
                    StepExecutionResult.succeeded(
                        output_asset_id=UUID("019f6000-0000-7000-8000-000000000041"),
                        asset_version=f"sha256:{'d' * 64}",
                        quality_status="passed",
                        download_allowed=True,
                        quality_report_schema_version=(
                            "presentation-quality-report.v1"
                        ),
                    ),
                    StepExecutionResult.permanent_failure(
                        "spreadsheet_quality_blocked",
                        quality_status="blocked",
                        download_allowed=False,
                        quality_report_schema_version=("workbook-quality-report.v1"),
                    ),
                ]
            ),
        )
        async with generation_harness.session_factory() as session, session.begin():
            task = await session.get(GenerationTask, task_id)
            session.add(
                FileAsset(
                    id=UUID("019f6000-0000-7000-8000-000000000041"),
                    user_id=task.user_id,
                    project_id=task.project_id,
                    original_filename="sales-presentation.pptx",
                    file_category="presentation",
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "presentationml.presentation"
                    ),
                    byte_size=1024,
                    sha256="d" * 64,
                    storage_provider="local",
                    storage_key=(
                        f"users/{task.user_id}/outputs/"
                        "019f6000-0000-7000-8000-000000000041/presentation.pptx"
                    ),
                    processing_status="ready",
                    generated_task_id=task.id,
                    quality_status="passed",
                    quality_report_key="internal",
                    quality_report_sha256="e" * 64,
                    quality_report_schema_version=("presentation-quality-report.v1"),
                    quality_engine_version="presentation-quality.v1",
                    quality_preview_keys=[],
                    quality_validated_key="internal",
                    quality_validated_sha256="d" * 64,
                    quality_validated_byte_size=1024,
                    quality_repair_attempt_count=0,
                    processing_warnings=[],
                )
            )
        outputs = await client.get(
            f"/api/v1/generations/{task_id}/outputs",
            headers={"Authorization": "Bearer access-token"},
        )

    assert created.status_code == 201
    assert outputs.status_code == 200
    assert outputs.headers["cache-control"] == "private, no-store"
    body = outputs.json()
    assert {item["output_kind"] for item in body["outputs"]} == {"pptx", "xlsx"}
    ppt = next(item for item in body["outputs"] if item["output_kind"] == "pptx")
    xlsx = next(item for item in body["outputs"] if item["output_kind"] == "xlsx")
    assert ppt["download_allowed"] is True
    assert ppt["asset_id"] is not None
    assert xlsx["download_allowed"] is False
    assert xlsx["asset_id"] is None
    assert "storage_key" not in str(body)
