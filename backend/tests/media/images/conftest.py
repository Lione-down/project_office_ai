from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from PIL import Image
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.chat_messages import ChatMessage
from app.models.chat_threads import ChatThread
from app.models.deck_draft_revisions import DeckDraftRevision
from app.models.deck_drafts import DeckDraft
from app.models.projects import Project
from app.models.provider_credentials import ProviderCredential
from app.models.users import User
from app.models.base import utc_now
from app.providers.agnes import ProviderImage
from app.services.auth_sessions import CurrentUser
from app.services.decks.contracts import DeckBrief, deck_content_checksum
from app.services.media.images.service import ImageJobService
from app.services.media.images.worker import ImageJobWorkerService
from app.storage.local import LocalStorageAdapter


USER_ID = UUID("019fad50-0000-7000-8000-000000000001")
OTHER_USER_ID = UUID("019fad50-0000-7000-8000-000000000002")
PROJECT_ID = UUID("019fad50-0000-7000-8000-000000000003")
PROVIDER_ID = UUID("019fad50-0000-7000-8000-000000000010")
CREDENTIAL_ID = UUID("019fad50-0000-7000-8000-000000000011")
MODEL_ID = UUID("019fad50-0000-7000-8000-000000000012")
THREAD_ID = UUID("019fad50-0000-7000-8000-000000000020")
MESSAGE_ID = UUID("019fad50-0000-7000-8000-000000000021")
DRAFT_ID = UUID("019fad50-0000-7000-8000-000000000022")
REVISION_ID = UUID("019fad50-0000-7000-8000-000000000023")
SLIDE_IDS = tuple(
    UUID(f"019fad50-0000-7000-8000-{index:012d}") for index in range(30, 33)
)


class Sessions:
    def __init__(self) -> None:
        self.user_id = USER_ID

    async def authenticate_access(self, _access_token: str) -> CurrentUser:
        return CurrentUser(
            user_id=self.user_id,
            phone_country_code="+86",
            phone_number="13800000000",
            role="user",
            status="active",
            credit_balance=10_000,
            must_change_password=False,
        )


class Cipher:
    def decrypt(self, _ciphertext: str) -> str:
        return "test-only-provider-key"


class ImageAdapter:
    def __init__(self) -> None:
        self.requests = []
        buffer = BytesIO()
        Image.new("RGB", (64, 36), color=(24, 72, 120)).save(buffer, "PNG")
        self.payload = buffer.getvalue()

    async def create_image(self, *, api_key, request):
        assert api_key == "test-only-provider-key"
        self.requests.append(request)
        return ProviderImage("provider-image-1", self.payload, 200)

    def classify_error(self, _exception):
        raise AssertionError("happy path must not classify")


def deck() -> DeckBrief:
    return DeckBrief.model_validate(
        {
            "schema_version": "deck-brief.v1",
            "topic": "季度经营复盘",
            "audience": "管理层",
            "language": "zh-CN",
            "style": "专业",
            "source_mode": "inspiration",
            "skill_code": "ppt.sales-business-review.v1",
            "slides": [
                {
                    "slide_id": str(slide_id),
                    "title": title,
                    "purpose": "说明本页目标",
                    "body": ["季度趋势", "关键行动"],
                    "speaker_notes": "",
                    "visual_suggestion": "专业商务插画",
                    "provenance": [{"kind": "agnes_inference", "evidence_ids": []}],
                }
                for slide_id, title in zip(
                    SLIDE_IDS,
                    ("封面", "趋势分析", "行动建议"),
                    strict=True,
                )
            ],
        }
    )


@dataclass
class ImageHarness:
    session_factory: async_sessionmaker
    sessions: Sessions
    service: ImageJobService
    worker: ImageJobWorkerService
    adapter: ImageAdapter
    storage: LocalStorageAdapter


@pytest_asyncio.fixture
async def image_harness(tmp_path) -> ImageHarness:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{(tmp_path / 'images.db').as_posix()}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    now = utc_now()
    content = deck()
    async with session_factory() as session, session.begin():
        session.add_all(
            [
                User(
                    id=USER_ID,
                    phone_country_code="+86",
                    phone_number="13800000000",
                    role="user",
                    status="active",
                    password_hash="hash",
                    credit_balance=10_000,
                    must_change_password=False,
                    invite_code_id=None,
                ),
                User(
                    id=OTHER_USER_ID,
                    phone_country_code="+86",
                    phone_number="13900000000",
                    role="user",
                    status="active",
                    password_hash="hash",
                    credit_balance=10_000,
                    must_change_password=False,
                    invite_code_id=None,
                ),
                AiProvider(
                    id=PROVIDER_ID,
                    vendor="agnes",
                    display_name="Agnes",
                    protocol="openai-compatible",
                    base_url="https://apihub.agnes-ai.com/v1",
                    status="active",
                    default_timeout_seconds=360,
                    config={},
                ),
                ProviderCredential(
                    id=CREDENTIAL_ID,
                    provider_id=PROVIDER_ID,
                    name="Image Contract",
                    encrypted_key="encrypted",
                    key_fingerprint="a" * 64,
                    status="active",
                    rpm_limit=60,
                    tpm_limit=100_000,
                    max_concurrency=2,
                    rotation_source="test",
                    created_by_user_id=None,
                ),
                AiModel(
                    id=MODEL_ID,
                    provider_id=PROVIDER_ID,
                    credential_id=CREDENTIAL_ID,
                    model_code="agnes-image-2.1-flash",
                    display_name="Agnes Image 2.1 Flash",
                    capabilities={
                        "image_generation": True,
                        "image_data_uri_input": True,
                        "credit_per_image": 12,
                    },
                    context_window=1,
                    max_output_tokens=1,
                    user_visible=True,
                    is_recommended=True,
                    credit_multiplier=Decimal("1.0000"),
                    allowed_skills=[],
                    status="active",
                ),
            ]
        )
        await session.flush()
        session.add(
            Project(
                id=PROJECT_ID,
                user_id=USER_ID,
                name="Image Project",
                is_default=True,
                is_archived=False,
                deleted_at=None,
            )
        )
        session.add(
            ChatThread(
                id=THREAD_ID,
                thread_id=THREAD_ID,
                user_id=USER_ID,
                title="Image Deck",
                default_model_id=MODEL_ID,
                mode="ppt",
                status="active",
                idempotency_key="image-thread-key",
                request_fingerprint="b" * 64,
                last_activity_at=now,
                retention_expires_at=now + timedelta(days=365),
                deleted_at=None,
            )
        )
        await session.flush()
        session.add(
            ChatMessage(
                id=MESSAGE_ID,
                thread_id=THREAD_ID,
                sequence=1,
                role="assistant",
                content="Synthetic deck",
                content_format="markdown",
                status="succeeded",
                parent_message_id=None,
                supersedes_message_id=None,
                branch_root_id=MESSAGE_ID,
                run_id=None,
                provenance_summary={},
                finalized_at=now,
            )
        )
        await session.flush()
        session.add(
            DeckDraft(
                id=DRAFT_ID,
                user_id=USER_ID,
                project_id=PROJECT_ID,
                thread_id=THREAD_ID,
                source_message_id=MESSAGE_ID,
                draft_group_id=DRAFT_ID,
                latest_revision=1,
                status="editing",
                idempotency_key="image-deck-key",
                request_fingerprint="c" * 64,
                deleted_at=None,
            )
        )
        await session.flush()
        session.add(
            DeckDraftRevision(
                id=REVISION_ID,
                draft_id=DRAFT_ID,
                revision=1,
                content=content.model_dump(mode="json"),
                content_checksum=deck_content_checksum(content),
                source_mode="inspiration",
                skill_snapshot={"skill_code": content.skill_code, "version": "1.0.0"},
                model_snapshot={"model_id": str(MODEL_ID)},
                template_snapshot={
                    "template_code": "ppt.executive-blue.v1",
                    "version": "1.0.0",
                    "checksum": "d" * 64,
                },
                provenance_summary={},
                preflight_snapshot=None,
                high_risk_confirmation_required=False,
                high_risk_confirmed_at=None,
                status="editing",
                bridge_brief_id=None,
                generation_task_id=None,
                confirmed_at=None,
            )
        )
    sessions = Sessions()
    storage = LocalStorageAdapter(tmp_path / "files")
    adapter = ImageAdapter()
    service = ImageJobService(
        session_factory,
        sessions,
        max_active_jobs_per_user=2,
        max_prompt_chars=4000,
    )
    worker = ImageJobWorkerService(
        session_factory,
        Cipher(),
        storage,
        adapter_factory=lambda _provider: adapter,
        max_image_bytes=20 * 1024 * 1024,
        max_decoded_bytes=128 * 1024 * 1024,
        provider_timeout_seconds=360,
    )
    try:
        yield ImageHarness(
            session_factory,
            sessions,
            service,
            worker,
            adapter,
            storage,
        )
    finally:
        await engine.dispose()
