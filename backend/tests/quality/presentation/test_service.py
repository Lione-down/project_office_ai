from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import (
    Base,
    FileAsset,
    GenerationTask,
    GenerationTaskStep,
    Project,
    User,
)
from app.models.base import utc_now
from app.services.quality.presentation.artifact_store import (
    PresentationQualityArtifactStore,
)
from app.services.quality.presentation.inspector import PresentationPackageInspector
from app.services.quality.presentation.libreoffice import (
    LibreOfficeArtifact,
    LibreOfficeConversion,
    LibreOfficePage,
)
from app.services.quality.presentation.repair import PresentationDeterministicRepair
from app.services.quality.presentation.service import PresentationQualityService
from app.services.renderers.presentation.contracts import (
    PresentationPlan,
    presentation_plan_sha256,
)
from app.services.renderers.presentation.output_store import PresentationOutputStore
from app.storage.local import LocalStorageAdapter
from tests.quality.presentation.samples import write_presentation_sample
from tests.renderers.presentation.test_contracts import valid_plan


USER_ID = UUID("019b0000-0000-7000-8000-000000000331")
PROJECT_ID = UUID("019b0000-0000-7000-8000-000000000332")
TASK_ID = UUID("019b0000-0000-7000-8000-000000000333")
STEP_ID = UUID("019b0000-0000-7000-8000-000000000334")
ASSET_ID = UUID("019b0000-0000-7000-8000-000000000335")


class FakeLibreOfficeClient:
    def __init__(self, root: Path, *, page_count: int = 3) -> None:
        self.root = root
        self.page_count = page_count
        self.calls: list[dict] = []

    async def convert(self, **request) -> LibreOfficeConversion:
        self.calls.append(request)
        call_root = self.root / f"call-{len(self.calls)}"
        call_root.mkdir()
        pdf = call_root / "preview.pdf"
        pdf.write_bytes(b"%PDF-synthetic-preview")
        pages: list[LibreOfficePage] = []
        for page_number in range(1, self.page_count + 1):
            page = call_root / f"page-{page_number:04d}.png"
            page.write_bytes(f"png-{page_number}".encode())
            pages.append(
                LibreOfficePage(
                    page,
                    page_number,
                    1280,
                    720,
                    sha256(page.read_bytes()).hexdigest(),
                    page.stat().st_size,
                )
            )
        return LibreOfficeConversion(
            libreoffice_version="LibreOffice 25.2.3",
            pdf=LibreOfficeArtifact(
                pdf,
                sha256(pdf.read_bytes()).hexdigest(),
                pdf.stat().st_size,
            ),
            pages=tuple(pages),
        )


@dataclass
class QualityHarness:
    service: PresentationQualityService
    libreoffice: FakeLibreOfficeClient
    session_factory: async_sessionmaker[AsyncSession]
    source: Path
    plan: dict


async def make_harness(
    tmp_path: Path,
    *,
    sample_options: dict | None = None,
    page_count: int = 3,
) -> QualityHarness:
    plan = valid_plan()
    sample = write_presentation_sample(
        tmp_path / "source.pptx",
        evidence_ids=("ev-1",),
        **(sample_options or {}),
    )
    files_root = tmp_path / "files"
    stored = PresentationOutputStore(files_root).persist(USER_ID, ASSET_ID, sample)
    plan_checksum = presentation_plan_sha256(PresentationPlan.model_validate(plan))
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session, session.begin():
        session.add_all(
            [
                User(
                    id=USER_ID,
                    phone_number="13800000331",
                    password_hash="test-hash",
                    credit_balance=5_000,
                ),
                Project(
                    id=PROJECT_ID,
                    user_id=USER_ID,
                    name="PPT Quality",
                    is_default=False,
                ),
                GenerationTask(
                    id=TASK_ID,
                    user_id=USER_ID,
                    project_id=PROJECT_ID,
                    brief_id=UUID("019b0000-0000-7000-8000-000000000336"),
                    model_id=UUID("019b0000-0000-7000-8000-000000000337"),
                    credential_id=UUID("019b0000-0000-7000-8000-000000000338"),
                    idempotency_key="quality-task",
                    status="running",
                    progress=0,
                    skill_snapshot=[],
                    model_snapshot={},
                    estimated_credits=800,
                    settled_credits=0,
                    timeout_at=utc_now(),
                ),
                GenerationTaskStep(
                    id=STEP_ID,
                    task_id=TASK_ID,
                    step_key="render:pptx",
                    output_kind="pptx",
                    status="running",
                    attempt=1,
                    estimated_credits=800,
                    checkpoint={
                        "provider_call_started": False,
                        "renderer_call_completed": True,
                        "output_asset_id": str(ASSET_ID),
                        "presentation_plan_checksum": plan_checksum,
                        "renderer_version": "ppt-renderer.v1",
                        "template_code": "ppt.executive-blue.v1",
                        "template_version": "1.0.0",
                        "slide_count": 3,
                        "renderer_result": {
                            "sha256": stored.sha256,
                            "byte_size": stored.byte_size,
                            "slide_count": 3,
                            "renderer_version": "ppt-renderer.v1",
                            "template_code": "ppt.executive-blue.v1",
                            "template_version": "1.0.0",
                            "plan_sha256": plan_checksum,
                        },
                    },
                    token_estimate=0,
                ),
                FileAsset(
                    id=ASSET_ID,
                    user_id=USER_ID,
                    project_id=PROJECT_ID,
                    original_filename="sales-presentation.pptx",
                    file_category="presentation",
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "presentationml.presentation"
                    ),
                    byte_size=stored.byte_size,
                    sha256=stored.sha256,
                    storage_provider="local",
                    storage_key=stored.storage_key,
                    processing_status="ready",
                    idempotency_key=f"render-output:{STEP_ID}",
                    generated_task_id=TASK_ID,
                    processing_warnings=[],
                    parser_name="pptxgenjs",
                    parser_version="ppt-renderer.v1",
                    processed_at=utc_now(),
                ),
            ]
        )
    libreoffice = FakeLibreOfficeClient(tmp_path / "libreoffice", page_count=page_count)
    libreoffice.root.mkdir()
    service = PresentationQualityService(
        session_factory,
        LocalStorageAdapter(files_root),
        PresentationQualityArtifactStore(files_root),
        PresentationPackageInspector(),
        PresentationDeterministicRepair(),
        libreoffice,
        temp_root=tmp_path / "quality-temp",
    )
    service._test_engine = engine
    return QualityHarness(service, libreoffice, session_factory, stored.path, plan)


async def test_quality_service_passes_and_replays_without_second_conversion(
    tmp_path: Path,
) -> None:
    harness = await make_harness(tmp_path)

    first = await harness.service.evaluate(ASSET_ID, STEP_ID, harness.plan)
    replay = await harness.service.evaluate(ASSET_ID, STEP_ID, harness.plan)

    assert first.report.status == "passed"
    assert first.report.download_allowed is True
    assert first.validated_key.endswith("/presentation.pptx")
    assert replay.replayed is True
    assert len(harness.libreoffice.calls) == 1
    async with harness.session_factory() as session:
        asset = await session.get(FileAsset, ASSET_ID)
        step = await session.get(GenerationTaskStep, STEP_ID)
    assert asset.quality_status == "passed"
    assert asset.quality_report_schema_version == "presentation-quality-report.v1"
    assert asset.quality_validated_key == asset.storage_key
    assert step.checkpoint["quality_status"] == "passed"


async def test_quality_service_replay_rejects_tampered_preview(
    tmp_path: Path,
) -> None:
    harness = await make_harness(tmp_path)
    first = await harness.service.evaluate(ASSET_ID, STEP_ID, harness.plan)
    preview = harness.source.parent / "quality" / "pages" / "page-0001.png"
    preview.write_bytes(b"tampered-preview")

    with pytest.raises(
        RuntimeError, match="presentation_quality_preview_integrity_failed"
    ):
        await harness.service.evaluate(ASSET_ID, STEP_ID, harness.plan)

    assert first.report.download_allowed is True
    assert len(harness.libreoffice.calls) == 1


async def test_quality_service_finalize_is_idempotent_after_db_race(
    tmp_path: Path,
) -> None:
    harness = await make_harness(tmp_path)
    first = await harness.service.evaluate(ASSET_ID, STEP_ID, harness.plan)
    plan = PresentationPlan.validate_for_renderer(harness.plan)
    pending = await harness.service._prepare(
        ASSET_ID,
        STEP_ID,
        plan,
        presentation_plan_sha256(plan),
    )
    report, stored = harness.service._artifacts.recover_report(USER_ID, ASSET_ID)

    replay = await harness.service._finalize(
        pending,
        report,
        stored,
        validated_key=first.validated_key,
        replayed=True,
    )

    assert replay.replayed is True
    assert replay.report_sha256 == first.report_sha256


async def test_quality_service_repairs_once_and_preserves_original(
    tmp_path: Path,
) -> None:
    harness = await make_harness(
        tmp_path,
        sample_options={"overflow_slide": 2, "long_title_slide": 3},
    )
    source_before = harness.source.read_bytes()

    outcome = await harness.service.evaluate(ASSET_ID, STEP_ID, harness.plan)

    assert outcome.report.status == "passed_with_warnings"
    assert outcome.report.repair_attempt_count == 1
    assert harness.source.read_bytes() == source_before
    assert outcome.validated_key.endswith("/quality/repaired.pptx")
    assert harness.libreoffice.calls[0]["source_variant"] == "repaired"
    assert {item.code for item in outcome.report.findings} == {
        "object_bounds_repaired",
        "title_autofit_applied",
    }
    replay = await harness.service.evaluate(ASSET_ID, STEP_ID, harness.plan)
    assert replay.replayed is True
    assert len(harness.libreoffice.calls) == 1


async def test_quality_service_blocks_unrepairable_sample_without_libreoffice(
    tmp_path: Path,
) -> None:
    harness = await make_harness(tmp_path, sample_options={"blank_slide": 2})

    outcome = await harness.service.evaluate(ASSET_ID, STEP_ID, harness.plan)

    assert outcome.report.status == "blocked"
    assert outcome.report.download_allowed is False
    assert "blank_slide" in {item.code for item in outcome.report.findings}
    assert harness.libreoffice.calls == []
    assert outcome.step_result().status == "permanent_failure"
    assert outcome.step_result().error_category == "presentation_quality_blocked"


async def test_quality_service_blocks_libreoffice_page_mismatch(
    tmp_path: Path,
) -> None:
    harness = await make_harness(tmp_path, page_count=2)

    outcome = await harness.service.evaluate(ASSET_ID, STEP_ID, harness.plan)

    assert outcome.report.status == "blocked"
    assert "libreoffice_page_count_mismatch" in {
        item.code for item in outcome.report.findings
    }
    assert outcome.report.libreoffice.status == "passed"
    assert len(outcome.report.previews) == 2
