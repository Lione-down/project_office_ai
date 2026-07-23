from collections.abc import AsyncIterator
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import (
    Base,
    GenerationTask,
    GenerationTaskInput,
    GenerationTaskStep,
    Project,
    User,
)
from app.models.base import utc_now
from app.services.renderers.presentation.client import RenderedPresentation
from app.services.renderers.presentation.contracts import (
    PresentationPlan,
    presentation_plan_sha256,
)
from app.services.renderers.presentation.output_store import PresentationOutputStore
from app.services.renderers.presentation.service import PresentationOutputService


USER_ID = UUID("019f5000-0000-7000-8000-000000000201")
PROJECT_ID = UUID("019f5000-0000-7000-8000-000000000202")
TASK_ID = UUID("019f5000-0000-7000-8000-000000000203")
STEP_ID = UUID("019f5000-0000-7000-8000-000000000204")


class FakeRendererClient:
    def __init__(self, source: Path) -> None:
        self.source = source
        self.calls: list[tuple[UUID, dict]] = []

    async def render(self, request_id: UUID, plan) -> RenderedPresentation:
        self.calls.append((request_id, plan))
        payload = self.source.read_bytes()
        plan_sha256 = presentation_plan_sha256(PresentationPlan.model_validate(plan))
        return RenderedPresentation(
            path=self.source,
            sha256=sha256(payload).hexdigest(),
            byte_size=len(payload),
            slide_count=len(plan["slides"]),
            template_code=plan["template"]["code"],
            template_version=plan["template"]["version"],
            renderer_version=plan["renderer_version"],
            plan_sha256=plan_sha256,
        )


class FailingRendererClient:
    async def render(self, request_id: UUID, plan) -> RenderedPresentation:
        raise RuntimeError("simulated renderer failure")


@dataclass
class OutputHarness:
    service: PresentationOutputService
    client: FakeRendererClient
    session_factory: async_sessionmaker[AsyncSession]
    output_store: PresentationOutputStore


@pytest_asyncio.fixture
async def output_harness(tmp_path: Path) -> AsyncIterator[OutputHarness]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session, session.begin():
        session.add_all(
            [
                User(
                    id=USER_ID,
                    phone_number="13800000201",
                    password_hash="test-hash",
                    credit_balance=5_000,
                ),
                Project(
                    id=PROJECT_ID,
                    user_id=USER_ID,
                    name="Renderer Contract",
                    is_default=False,
                ),
                GenerationTask(
                    id=TASK_ID,
                    user_id=USER_ID,
                    project_id=PROJECT_ID,
                    brief_id=UUID("019f5000-0000-7000-8000-000000000205"),
                    model_id=UUID("019f5000-0000-7000-8000-000000000206"),
                    credential_id=UUID("019f5000-0000-7000-8000-000000000207"),
                    idempotency_key="renderer-contract-task",
                    status="running",
                    progress=0,
                    skill_snapshot=[
                        {
                            "skill_code": "ppt.sales-business-review.v1",
                            "version": "1.0.0",
                            "kind": "pptx",
                            "template_code": "ppt.executive-blue.v1",
                            "template_version": "1.0.0",
                            "estimated_credits": 800,
                        }
                    ],
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
                    checkpoint={"provider_call_started": False},
                    token_estimate=0,
                ),
                GenerationTaskInput(
                    task_id=TASK_ID,
                    input_type="template",
                    reference_key="ppt.executive-blue.v1@1.0.0",
                    snapshot={
                        "template_code": "ppt.executive-blue.v1",
                        "version": "1.0.0",
                        "output_kind": "pptx",
                    },
                ),
            ]
        )
    source = tmp_path / "renderer-work.pptx"
    source.write_bytes(b"synthetic-renderer-output")
    client = FakeRendererClient(source)
    output_store = PresentationOutputStore(tmp_path / "files")
    yield OutputHarness(
        service=PresentationOutputService(
            session_factory,
            client,
            output_store,
        ),
        client=client,
        session_factory=session_factory,
        output_store=output_store,
    )
    await engine.dispose()
