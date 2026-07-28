from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.provider_credentials import ProviderCredential
from app.models.users import User
from app.providers.agnes import ProviderStreamChunk, ProviderUsage
from app.services.auth_sessions import CurrentUser
from app.services.chat import ChatService
from app.settings.config import Settings


USER_ID = UUID("019fa9dc-0000-7000-8000-000000000001")
OTHER_USER_ID = UUID("019fa9dc-0000-7000-8000-000000000002")
PROVIDER_ID = UUID("019fa9dc-0000-7000-8000-000000000010")
CREDENTIAL_ID = UUID("019fa9dc-0000-7000-8000-000000000011")
MODEL_25_ID = UUID("019fa9dc-0000-7000-8000-000000000025")
MODEL_20_ID = UUID("019fa9dc-0000-7000-8000-000000000020")


class Sessions:
    def __init__(self, user_id: UUID = USER_ID) -> None:
        self.user_id = user_id

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


class Admission:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int, int]] = []

    async def check(
        self,
        scope: str,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        self.calls.append((scope, key, limit, window_seconds))


class StreamAdapter:
    def __init__(self) -> None:
        self.requests = []

    async def stream_chat_completion(self, *, api_key, request):
        assert api_key == "test-only-provider-key"
        self.requests.append(request)
        yield ProviderStreamChunk(
            provider_request_id="provider-stream-1",
            content_delta="第一段",
        )
        yield ProviderStreamChunk(content_delta="第二段")
        yield ProviderStreamChunk(
            finish_reason="stop",
            usage=ProviderUsage(12, 7, 19),
        )

    def classify_error(self, _error):
        raise AssertionError("happy path must not classify an error")


@dataclass
class ChatHarness:
    session_factory: async_sessionmaker
    service: ChatService
    sessions: Sessions
    adapter: StreamAdapter
    admission: Admission


@pytest_asyncio.fixture
async def chat_harness(tmp_path) -> ChatHarness:
    database_path = tmp_path / "chat-service.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
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
                    default_timeout_seconds=120,
                    config={},
                ),
                ProviderCredential(
                    id=CREDENTIAL_ID,
                    provider_id=PROVIDER_ID,
                    name="Chat Contract",
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
                    id=MODEL_25_ID,
                    provider_id=PROVIDER_ID,
                    credential_id=CREDENTIAL_ID,
                    model_code="agnes-2.5-flash",
                    display_name="Agnes 2.5 Flash",
                    capabilities={
                        "chat_stream": True,
                        "thinking": True,
                        "tool_calling": False,
                    },
                    context_window=262_144,
                    max_output_tokens=8192,
                    user_visible=True,
                    is_recommended=True,
                    credit_multiplier=Decimal("1.0000"),
                    allowed_skills=[],
                    status="active",
                ),
                AiModel(
                    id=MODEL_20_ID,
                    provider_id=PROVIDER_ID,
                    credential_id=CREDENTIAL_ID,
                    model_code="agnes-2.0-flash",
                    display_name="Agnes 2.0 Flash",
                    capabilities={
                        "chat_stream": True,
                        "thinking": False,
                        "tool_calling": False,
                    },
                    context_window=262_144,
                    max_output_tokens=8192,
                    user_visible=True,
                    is_recommended=False,
                    credit_multiplier=Decimal("1.0000"),
                    allowed_skills=[],
                    status="active",
                ),
            ]
        )
    sessions = Sessions()
    adapter = StreamAdapter()
    admission = Admission()
    service = ChatService(
        session_factory,
        sessions,
        Cipher(),
        settings=Settings(
            OFFICE_AI_DATABASE_URL="sqlite+aiosqlite:///:memory:",
            OFFICE_AI_REDIS_URL="redis://redis:6379/0",
        ),
        adapter_factory=lambda _provider: adapter,
        admission_limiter=admission,
    )
    harness = ChatHarness(
        session_factory=session_factory,
        service=service,
        sessions=sessions,
        adapter=adapter,
        admission=admission,
    )
    try:
        yield harness
    finally:
        await engine.dispose()
