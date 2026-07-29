from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import (
    AiModel,
    AiProvider,
    Base,
    ChatMessage,
    ChatThread,
    CreditLedger,
    DeckDraft,
    DeckDraftInput,
    DeckDraftRevision,
    FileAsset,
    Project,
    ProviderCredential,
    Skill,
    User,
    WorkflowTask,
)
from app.providers.agnes import ProviderCompletion, ProviderUsage
from app.services.auth_sessions import CurrentUser
from app.services.decks.contracts import (
    DeckConfirmCommand,
    DeckCreateCommand,
    DeckGenerationCommand,
    DeckUpdateCommand,
)
from app.services.decks.service import DeckOperationError, DeckService
from app.services.evidence.store import EvidenceManifestStore
from app.services.generation import GenerationService
from app.services.generation_runtime import PresentationGenerationPipeline
from app.services.generation_worker import StepExecutionContext, StepExecutionResult
from app.services.chat_persistence import chat_message_snapshot
from app.services.preflight.service import BriefWorkflowService
from app.skills.catalog import KNOWLEDGE_EDUCATION_SKILL
from tests.decks.test_contracts import valid_deck_payload


USER_ID = UUID("019fad10-0000-7000-8000-000000000001")
OTHER_USER_ID = UUID("019fad10-0000-7000-8000-000000000002")
PROJECT_ID = UUID("019fad10-0000-7000-8000-000000000003")
PROVIDER_ID = UUID("019fad10-0000-7000-8000-000000000004")
CREDENTIAL_ID = UUID("019fad10-0000-7000-8000-000000000005")
MODEL_ID = UUID("019fad10-0000-7000-8000-000000000006")
THREAD_ID = UUID("019fad10-0000-7000-8000-000000000007")
MESSAGE_ID = UUID("019fad10-0000-7000-8000-000000000008")
FAILED_MESSAGE_ID = UUID("019fad10-0000-7000-8000-000000000009")
OTHER_MESSAGE_ID = UUID("019fad10-0000-7000-8000-000000000010")
ASSET_ID = UUID("019fad10-0000-7000-8000-000000000011")


class Sessions:
    async def authenticate_access(self, access_token: str) -> CurrentUser:
        user_id = USER_ID if access_token == "access-token" else OTHER_USER_ID
        return CurrentUser(
            user_id=user_id,
            phone_country_code="+86",
            phone_number="13800000000",
            role="user",
            status="active",
            credit_balance=10_000,
            must_change_password=False,
        )


class Cipher:
    def decrypt(self, _ciphertext: str) -> str:
        return "test-only-key"


class Adapter:
    def __init__(self, payloads: list[str]) -> None:
        self.payloads = payloads
        self.requests = []

    async def create_chat_completion(self, *, api_key, request):
        assert api_key == "test-only-key"
        self.requests.append(request)
        content = self.payloads.pop(0)
        return ProviderCompletion(
            provider_request_id=f"provider-{len(self.requests)}",
            content=content,
            usage=ProviderUsage(100, 80, 180),
            finish_reason="stop",
            status_summary=200,
        )

    def classify_error(self, _error):
        raise AssertionError("provider error classification is not expected")


@dataclass
class DeckHarness:
    session_factory: async_sessionmaker[AsyncSession]
    service: DeckService
    adapter: Adapter


def command() -> DeckCreateCommand:
    return DeckCreateCommand(
        project_id=PROJECT_ID,
        model_id=MODEL_ID,
        topic="用通俗方式解释生成式 AI",
        audience="没有技术背景的业务团队",
        slide_count=3,
        language="zh-CN",
        style="清晰、克制、适合培训",
        source_mode="inspiration",
        skill_code="ppt.knowledge-education.v1",
        asset_ids=(),
    )


@pytest.mark.asyncio
async def test_runtime_deck_limits_fail_before_provider_or_persistence() -> None:
    service = DeckService(
        None,
        None,
        None,
        max_slides=3,
        max_context_assets=1,
    )

    with pytest.raises(DeckOperationError) as error:
        await service.create(
            "access-token",
            MESSAGE_ID,
            command().model_copy(update={"slide_count": 4}),
            "deck-create-limit",
            trace_id="trace-deck-limit",
        )

    assert error.value.error_code == "deck_limit_exceeded"


@pytest_asyncio.fixture
async def deck_harness(tmp_path) -> AsyncIterator[DeckHarness]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC).replace(tzinfo=None)
    async with session_factory() as session, session.begin():
        session.add_all(
            [
                User(
                    id=USER_ID,
                    phone_number="13800000000",
                    password_hash="hash",
                    credit_balance=10_000,
                ),
                User(
                    id=OTHER_USER_ID,
                    phone_number="13900000000",
                    password_hash="hash",
                    credit_balance=10_000,
                ),
                Project(
                    id=PROJECT_ID,
                    user_id=USER_ID,
                    name="知识培训",
                    is_default=False,
                ),
                AiProvider(
                    id=PROVIDER_ID,
                    vendor="agnes",
                    display_name="Agnes",
                    protocol="openai-compatible",
                    base_url="https://apihub.agnes-ai.com/v1",
                    status="active",
                    default_timeout_seconds=120,
                    config={},
                ),
                ProviderCredential(
                    id=CREDENTIAL_ID,
                    provider_id=PROVIDER_ID,
                    name="Deck",
                    encrypted_key="encrypted",
                    key_fingerprint="f" * 64,
                    status="active",
                    rpm_limit=60,
                    tpm_limit=100_000,
                    max_concurrency=2,
                    rotation_source="test",
                ),
                AiModel(
                    id=MODEL_ID,
                    provider_id=PROVIDER_ID,
                    credential_id=CREDENTIAL_ID,
                    model_code="agnes-2.5-flash",
                    display_name="Agnes 2.5 Flash",
                    capabilities={
                        "text_generation": True,
                        "structured_output": True,
                        "chat_stream": True,
                    },
                    context_window=262_144,
                    max_output_tokens=8192,
                    user_visible=True,
                    is_recommended=True,
                    credit_multiplier=Decimal("1.0000"),
                    allowed_skills=[KNOWLEDGE_EDUCATION_SKILL.skill_code],
                    status="active",
                ),
                Skill(
                    skill_code=KNOWLEDGE_EDUCATION_SKILL.skill_code,
                    version=KNOWLEDGE_EDUCATION_SKILL.version,
                    kind=KNOWLEDGE_EDUCATION_SKILL.kind,
                    display_name=KNOWLEDGE_EDUCATION_SKILL.display_name,
                    description=KNOWLEDGE_EDUCATION_SKILL.description,
                    output_kind=KNOWLEDGE_EDUCATION_SKILL.output_kind,
                    input_schema=KNOWLEDGE_EDUCATION_SKILL.input_schema,
                    output_schema=KNOWLEDGE_EDUCATION_SKILL.output_schema,
                    workflow=KNOWLEDGE_EDUCATION_SKILL.workflow,
                    capability_requirements=(
                        KNOWLEDGE_EDUCATION_SKILL.capability_requirements
                    ),
                    status=KNOWLEDGE_EDUCATION_SKILL.status,
                    checksum=KNOWLEDGE_EDUCATION_SKILL.checksum,
                ),
                ChatThread(
                    id=THREAD_ID,
                    thread_id=THREAD_ID,
                    user_id=USER_ID,
                    title="生成式 AI 培训",
                    default_model_id=MODEL_ID,
                    mode="ppt",
                    status="active",
                    idempotency_key="thread-create-1",
                    request_fingerprint="a" * 64,
                    last_activity_at=now,
                    retention_expires_at=now + timedelta(days=365),
                ),
                ChatMessage(
                    id=MESSAGE_ID,
                    thread_id=THREAD_ID,
                    sequence=1,
                    role="assistant",
                    content="请从定义、边界和行动建议组织培训。",
                    status="succeeded",
                    branch_root_id=MESSAGE_ID,
                    finalized_at=now,
                ),
                FileAsset(
                    id=ASSET_ID,
                    user_id=USER_ID,
                    project_id=PROJECT_ID,
                    original_filename="source.xlsx",
                    file_category="spreadsheet",
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    byte_size=128,
                    sha256="b" * 64,
                    storage_provider="local",
                    storage_key=f"users/{USER_ID}/quarantine/{ASSET_ID}/original.xlsx",
                    processing_status="ready",
                    manifest_key=f"users/{USER_ID}/assets/{ASSET_ID}/evidence.json",
                    manifest_status="valid",
                    manifest_sha256="c" * 64,
                    manifest_schema_version="evidence-manifest.v1",
                    evidence_engine_version="1.0.0",
                    evidence_warning_count=0,
                    evidence_blocker_count=0,
                ),
                ChatMessage(
                    id=FAILED_MESSAGE_ID,
                    thread_id=THREAD_ID,
                    sequence=2,
                    role="assistant",
                    content="未完成内容",
                    status="failed",
                    branch_root_id=FAILED_MESSAGE_ID,
                    finalized_at=now,
                ),
                ChatMessage(
                    id=OTHER_MESSAGE_ID,
                    thread_id=THREAD_ID,
                    sequence=3,
                    role="assistant",
                    content="请为第二份独立大纲组织内容。",
                    status="succeeded",
                    branch_root_id=OTHER_MESSAGE_ID,
                    finalized_at=now,
                ),
            ]
        )
    adapter = Adapter([json.dumps(valid_deck_payload(), ensure_ascii=False)] * 8)
    workflow = BriefWorkflowService(
        session_factory,
        Sessions(),
        EvidenceManifestStore(tmp_path / "evidence", max_output_bytes=64 * 1024),
    )
    generation = GenerationService(session_factory, Sessions())
    service = DeckService(
        session_factory,
        Sessions(),
        Cipher(),
        adapter_factory=lambda _provider: adapter,
        brief_workflow=workflow,
        generation=generation,
    )
    yield DeckHarness(session_factory, service, adapter)
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_persists_one_revision_and_replays_without_provider_call(
    deck_harness: DeckHarness,
) -> None:
    first = await deck_harness.service.create(
        "access-token",
        MESSAGE_ID,
        command(),
        "deck-create-0001",
        trace_id="trace-deck-create",
    )
    replay = await deck_harness.service.create(
        "access-token",
        MESSAGE_ID,
        command(),
        "deck-create-0001",
        trace_id="trace-deck-replay",
    )
    source_replay = await deck_harness.service.create(
        "access-token",
        MESSAGE_ID,
        command(),
        "deck-create-same-source",
        trace_id="trace-deck-source-replay",
    )

    assert first.revision == 1
    assert first.status == "draft"
    assert first.content.schema_version == "deck-brief.v1"
    assert replay.draft_id == first.draft_id
    assert replay.replayed is True
    assert source_replay.draft_id == first.draft_id
    assert source_replay.replayed is True
    assert len(deck_harness.adapter.requests) == 1
    async with deck_harness.session_factory() as session:
        assert await session.scalar(select(func.count(DeckDraft.id))) == 1
        assert await session.scalar(select(func.count(DeckDraftRevision.id))) == 1


@pytest.mark.asyncio
async def test_create_rejects_non_success_and_cross_owner_messages(
    deck_harness: DeckHarness,
) -> None:
    with pytest.raises(DeckOperationError) as failed:
        await deck_harness.service.create(
            "access-token",
            FAILED_MESSAGE_ID,
            command(),
            "deck-create-0002",
            trace_id="trace-deck-failed",
        )
    assert failed.value.error_code == "chat_message_not_found"

    with pytest.raises(DeckOperationError) as cross_owner:
        await deck_harness.service.create(
            "other-token",
            MESSAGE_ID,
            command(),
            "deck-create-0003",
            trace_id="trace-deck-owner",
        )
    assert cross_owner.value.error_code == "chat_message_not_found"
    assert len(deck_harness.adapter.requests) == 0


@pytest.mark.asyncio
async def test_outline_director_repairs_once_and_never_persists_invalid_content(
    deck_harness: DeckHarness,
) -> None:
    deck_harness.adapter.payloads = [
        '{"schema_version":"deck-brief.v1"}',
        json.dumps(valid_deck_payload(), ensure_ascii=False),
    ]

    created = await deck_harness.service.create(
        "access-token",
        MESSAGE_ID,
        command(),
        "deck-create-0004",
        trace_id="trace-deck-repair",
    )

    assert created.revision == 1
    assert len(deck_harness.adapter.requests) == 2

    deck_harness.adapter.payloads = ["{}", "{}"]
    with pytest.raises(DeckOperationError) as invalid:
        await deck_harness.service.create(
            "access-token",
            OTHER_MESSAGE_ID,
            command(),
            "deck-create-0005",
            trace_id="trace-deck-invalid",
        )
    assert invalid.value.error_code == "deck_schema_invalid"
    async with deck_harness.session_factory() as session:
        assert await session.scalar(select(func.count(DeckDraft.id))) == 1


@pytest.mark.asyncio
async def test_update_creates_immutable_revision_and_rejects_stale_revision(
    deck_harness: DeckHarness,
) -> None:
    created = await deck_harness.service.create(
        "access-token",
        MESSAGE_ID,
        command(),
        "deck-create-0006",
        trace_id="trace-deck-update",
    )
    edited = created.content.model_copy(
        update={
            "slides": tuple(
                [
                    created.content.slides[1],
                    created.content.slides[0],
                    created.content.slides[2].model_copy(update={"title": "开始行动"}),
                ]
            )
        }
    )

    revised = await deck_harness.service.update(
        "access-token",
        created.draft_id,
        DeckUpdateCommand(expected_revision=1, content=edited),
    )

    assert revised.revision == 2
    assert revised.status == "editing"
    assert revised.content.slides[0].slide_id == created.content.slides[1].slide_id
    assert created.content_checksum != revised.content_checksum
    with pytest.raises(DeckOperationError) as stale:
        await deck_harness.service.update(
            "access-token",
            created.draft_id,
            DeckUpdateCommand(expected_revision=1, content=edited),
        )
    assert stale.value.error_code == "deck_revision_stale"


@pytest.mark.asyncio
async def test_materials_mode_freezes_only_owned_ready_valid_assets(
    deck_harness: DeckHarness,
) -> None:
    materials_payload = valid_deck_payload()
    materials_payload["source_mode"] = "materials"
    materials_payload["skill_code"] = "ppt.sales-business-review.v1"
    materials_payload["slides"][0]["provenance"] = [
        {
            "kind": "source_evidence",
            "evidence_ids": [f"e-{'d' * 64}"],
        }
    ]
    deck_harness.adapter.payloads = [json.dumps(materials_payload, ensure_ascii=False)]
    materials_command = command().model_copy(
        update={
            "source_mode": "materials",
            "skill_code": "ppt.sales-business-review.v1",
            "asset_ids": (ASSET_ID,),
        }
    )
    async with deck_harness.session_factory() as session, session.begin():
        model = await session.get(AiModel, MODEL_ID, with_for_update=True)
        model.allowed_skills = [
            *model.allowed_skills,
            "ppt.sales-business-review.v1",
        ]
        from app.skills.catalog import ALPHA_SKILLS

        sales_skill = ALPHA_SKILLS[0]
        session.add(
            Skill(
                skill_code=sales_skill.skill_code,
                version=sales_skill.version,
                kind=sales_skill.kind,
                display_name=sales_skill.display_name,
                description=sales_skill.description,
                output_kind=sales_skill.output_kind,
                input_schema=sales_skill.input_schema,
                output_schema=sales_skill.output_schema,
                workflow=sales_skill.workflow,
                capability_requirements=sales_skill.capability_requirements,
                status=sales_skill.status,
                checksum=sales_skill.checksum,
            )
        )

    created = await deck_harness.service.create(
        "access-token",
        MESSAGE_ID,
        materials_command,
        "deck-create-0007",
        trace_id="trace-deck-assets",
    )

    async with deck_harness.session_factory() as session:
        asset_input = await session.scalar(
            select(DeckDraftInput).where(
                DeckDraftInput.revision_id == created.revision_id,
                DeckDraftInput.source_asset_id == ASSET_ID,
            )
        )
        assert asset_input.source_version == f"sha256:{'b' * 64}"
        assert asset_input.source_checksum == "b" * 64
        assert asset_input.evidence_snapshot["manifest_sha256"] == "c" * 64

    async with deck_harness.session_factory() as session, session.begin():
        asset = await session.get(FileAsset, ASSET_ID, with_for_update=True)
        asset.manifest_status = "invalid"
    deck_harness.adapter.requests.clear()
    with pytest.raises(DeckOperationError) as invalid:
        await deck_harness.service.create(
            "access-token",
            OTHER_MESSAGE_ID,
            materials_command,
            "deck-create-0008",
            trace_id="trace-deck-assets-invalid",
        )
    assert invalid.value.error_code == "deck_evidence_invalid"
    assert deck_harness.adapter.requests == []


@pytest.mark.asyncio
async def test_confirm_preflight_and_generation_reuse_authoritative_workflow(
    deck_harness: DeckHarness,
) -> None:
    created = await deck_harness.service.create(
        "access-token",
        MESSAGE_ID,
        command(),
        "deck-create-0009",
        trace_id="trace-deck-handoff",
    )
    confirmed = await deck_harness.service.confirm(
        "access-token",
        created.draft_id,
        DeckConfirmCommand(expected_revision=1),
    )
    ready = await deck_harness.service.preflight(
        "access-token",
        created.draft_id,
    )

    assert confirmed.status == "confirmed"
    assert ready.status == "ready"
    assert ready.preflight_snapshot["estimated_credits"] == 800
    assert ready.preflight_snapshot["has_blockers"] is False
    assert ready.preflight_snapshot["outputs"] == [
        {
            "skill_code": "ppt.knowledge-education.v1",
            "kind": "pptx",
            "title": "用通俗方式解释生成式 AI",
            "template_code": "ppt.executive-blue.v1",
            "template_version": "1.0.0",
            "estimated_credits": 800,
        }
    ]

    first = await deck_harness.service.generate(
        "access-token",
        created.draft_id,
        DeckGenerationCommand(
            expected_revision=1,
            accepted_estimated_credits=800,
        ),
        "deck-generation-0001",
    )
    replay = await deck_harness.service.generate(
        "access-token",
        created.draft_id,
        DeckGenerationCommand(
            expected_revision=1,
            accepted_estimated_credits=800,
        ),
        "deck-generation-0001",
    )

    assert first.task_id == replay.task_id
    assert first.status == "queued"
    assert replay.replayed is True
    async with deck_harness.session_factory() as session:
        revision = await session.get(DeckDraftRevision, created.revision_id)
        workflow = await session.scalar(
            select(WorkflowTask).where(WorkflowTask.brief_group_id == revision.draft_id)
        )
        if workflow is None:
            workflow = await session.scalar(
                select(WorkflowTask).where(
                    WorkflowTask.generation_task_id == first.task_id
                )
            )
        assert revision.status == "generation_queued"
        assert revision.generation_task_id == first.task_id
        assert workflow.generation_task_id == first.task_id
        assert workflow.status == "queued"
        source_message = await session.get(ChatMessage, MESSAGE_ID)
        projection = await chat_message_snapshot(session, source_message)
        assert projection.deck_draft_id == created.draft_id
        assert projection.deck_status == "generation_queued"
        assert projection.generation_task_id == first.task_id
        assert projection.generation_status == "queued"
        assert (
            await session.scalar(
                select(func.count(CreditLedger.id)).where(
                    CreditLedger.task_id == first.task_id,
                    CreditLedger.entry_type == "generation_reserve",
                )
            )
            == 1
        )


@pytest.mark.asyncio
async def test_high_risk_deck_requires_explicit_confirmation(
    deck_harness: DeckHarness,
) -> None:
    payload = valid_deck_payload()
    payload["topic"] = "医学诊断培训"
    deck_harness.adapter.payloads = [json.dumps(payload, ensure_ascii=False)]
    created = await deck_harness.service.create(
        "access-token",
        MESSAGE_ID,
        command().model_copy(update={"topic": "医学诊断培训"}),
        "deck-create-0010",
        trace_id="trace-deck-high-risk",
    )

    with pytest.raises(DeckOperationError) as blocked:
        await deck_harness.service.confirm(
            "access-token",
            created.draft_id,
            DeckConfirmCommand(expected_revision=1),
        )
    assert blocked.value.error_code == "high_risk_confirmation_required"

    confirmed = await deck_harness.service.confirm(
        "access-token",
        created.draft_id,
        DeckConfirmCommand(expected_revision=1, high_risk_confirmed=True),
    )
    assert confirmed.status == "confirmed"


class RecordingDeckOutput:
    def __init__(self) -> None:
        self.plans = []

    async def render(self, _task_id, _step_id, plan):
        self.plans.append(plan)
        return type(
            "Output",
            (),
            {"asset_id": UUID("019fad10-0000-7000-8000-000000000099")},
        )()


class PassingDeckQuality:
    async def evaluate(self, asset_id, _step_id, _plan):
        return type(
            "Outcome",
            (),
            {
                "step_result": lambda _self: StepExecutionResult.succeeded(
                    output_asset_id=asset_id,
                    asset_version=f"sha256:{'e' * 64}",
                    quality_status="passed",
                    download_allowed=True,
                    quality_report_schema_version="presentation-quality-report.v1",
                )
            },
        )()


@pytest.mark.asyncio
async def test_generation_pipeline_compiles_the_frozen_deck_revision(
    deck_harness: DeckHarness,
) -> None:
    created = await deck_harness.service.create(
        "access-token",
        MESSAGE_ID,
        command(),
        "deck-create-0011",
        trace_id="trace-deck-runtime",
    )
    await deck_harness.service.confirm(
        "access-token",
        created.draft_id,
        DeckConfirmCommand(expected_revision=1),
    )
    await deck_harness.service.preflight("access-token", created.draft_id)
    generation = await deck_harness.service.generate(
        "access-token",
        created.draft_id,
        DeckGenerationCommand(
            expected_revision=1,
            accepted_estimated_credits=800,
        ),
        "deck-generation-0002",
    )
    output = RecordingDeckOutput()
    pipeline = PresentationGenerationPipeline(
        deck_harness.session_factory,
        output,
        PassingDeckQuality(),
    )

    result = await pipeline.execute(
        StepExecutionContext(
            task_id=generation.task_id,
            step_id=UUID("019fad10-0000-7000-8000-000000000098"),
            step_key="render:pptx",
            output_kind="pptx",
            attempt=1,
            model_snapshot={},
        )
    )

    assert result.status == "succeeded"
    assert [slide["title"] for slide in output.plans[0]["slides"]] == [
        "生成式 AI 是什么",
        "适合与不适合的任务",
        "下一步",
    ]
    assert output.plans[0]["metadata"]["revision"] == "1"
