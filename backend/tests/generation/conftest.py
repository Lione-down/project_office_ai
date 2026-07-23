from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import (
    AiModel,
    AiProvider,
    Base,
    Brief,
    Project,
    ProviderCredential,
    User,
)
from app.services.auth_sessions import CurrentUser
from app.services.generation import GenerationService


USER_ID = UUID("019f5000-0000-7000-8000-000000000001")
OTHER_USER_ID = UUID("019f5000-0000-7000-8000-000000000002")
PROJECT_ID = UUID("019f5000-0000-7000-8000-000000000003")
PROVIDER_ID = UUID("019f5000-0000-7000-8000-000000000004")
CREDENTIAL_ID = UUID("019f5000-0000-7000-8000-000000000005")
MODEL_ID = UUID("019f5000-0000-7000-8000-000000000006")
BRIEF_ID = UUID("019f5000-0000-7000-8000-000000000007")
BRIEF_GROUP_ID = UUID("019f5000-0000-7000-8000-000000000008")
ASSET_ID = UUID("019f5000-0000-7000-8000-000000000009")


class FakeSessions:
    async def authenticate_access(self, access_token: str) -> CurrentUser:
        user_id = USER_ID if access_token == "access-token" else OTHER_USER_ID
        return CurrentUser(
            user_id=user_id,
            phone_country_code="+86",
            phone_number="13800000000",
            role="user",
            status="active",
            credit_balance=5_000,
            must_change_password=False,
        )


def confirmed_preflight(*, combined: bool = False) -> dict:
    outputs = [
        {
            "skill_code": "ppt.sales-business-review.v1",
            "kind": "pptx",
            "title": "销售经营汇报",
            "template_code": "ppt.executive-blue.v1",
            "template_version": "1.0.0",
            "estimated_credits": 800,
        }
    ]
    if combined:
        outputs.append(
            {
                "skill_code": "excel.sales-analysis-dashboard.v1",
                "kind": "xlsx",
                "title": "销售分析看板",
                "template_code": "excel.executive-dashboard.v1",
                "template_version": "1.0.0",
                "estimated_credits": 800,
            }
        )
    return {
        "brief_id": str(BRIEF_ID),
        "brief_group_id": str(BRIEF_GROUP_ID),
        "revision": 1,
        "status": "queued",
        "conflicts": [],
        "outputs": outputs,
        "credit_multiplier": "1.0000",
        "estimated_credits": sum(item["estimated_credits"] for item in outputs),
        "has_blockers": False,
        "confirmed_at": datetime(2026, 7, 23, 12, 0, tzinfo=UTC).isoformat(),
    }


@dataclass
class GenerationHarness:
    service: GenerationService
    session_factory: async_sessionmaker[AsyncSession]

    async def set_combined(self) -> None:
        async with self.session_factory() as session, session.begin():
            brief = await session.get(Brief, BRIEF_ID, with_for_update=True)
            brief.preflight_snapshot = confirmed_preflight(combined=True)
            brief.estimated_credits = 1_600
            brief.source_snapshot = {
                **brief.source_snapshot,
                "selected_skills": [
                    *brief.source_snapshot["selected_skills"],
                    {
                        "skill_code": "excel.sales-analysis-dashboard.v1",
                        "version": "1.0.0",
                    },
                ],
            }


@pytest_asyncio.fixture
async def generation_harness() -> AsyncIterator[GenerationHarness]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session, session.begin():
        session.add_all(
            [
                User(
                    id=USER_ID,
                    phone_number="13800000000",
                    password_hash="test-hash",
                    credit_balance=5_000,
                ),
                User(
                    id=OTHER_USER_ID,
                    phone_number="13900000000",
                    password_hash="test-hash",
                    credit_balance=5_000,
                ),
                Project(
                    id=PROJECT_ID,
                    user_id=USER_ID,
                    name="销售项目",
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
                    name="Agnes Alpha",
                    encrypted_key="encrypted",
                    key_fingerprint="f" * 64,
                    status="active",
                    rpm_limit=60,
                    tpm_limit=100_000,
                    max_concurrency=2,
                    rotation_source="initial",
                ),
                AiModel(
                    id=MODEL_ID,
                    provider_id=PROVIDER_ID,
                    credential_id=CREDENTIAL_ID,
                    model_code="agnes-2.0-flash",
                    display_name="Agnes 2.0 Flash",
                    capabilities={
                        "text_generation": True,
                        "structured_output": True,
                    },
                    context_window=4096,
                    max_output_tokens=512,
                    user_visible=True,
                    is_recommended=True,
                    credit_multiplier="1.0000",
                    allowed_skills=[
                        "ppt.sales-business-review.v1",
                        "excel.sales-analysis-dashboard.v1",
                    ],
                    status="active",
                ),
                Brief(
                    id=BRIEF_ID,
                    brief_group_id=BRIEF_GROUP_ID,
                    revision=1,
                    user_id=USER_ID,
                    project_id=PROJECT_ID,
                    selected_model_id=MODEL_ID,
                    source_snapshot={
                        "source_asset_versions": [
                            {
                                "asset_id": str(ASSET_ID),
                                "asset_version": f"sha256:{'a' * 64}",
                            }
                        ],
                        "term_library_versions": [],
                        "selected_skills": [
                            {
                                "skill_code": "ppt.sales-business-review.v1",
                                "version": "1.0.0",
                            }
                        ],
                        "selected_model": {
                            "model_id": str(MODEL_ID),
                            "provider_id": str(PROVIDER_ID),
                            "credential_id": str(CREDENTIAL_ID),
                            "model_code": "agnes-2.0-flash",
                        },
                        "template_versions": [
                            {
                                "template_code": "ppt.executive-blue.v1",
                                "version": "1.0.0",
                            }
                        ],
                    },
                    content={},
                    content_checksum="a" * 64,
                    status="queued",
                    preflight_snapshot=confirmed_preflight(),
                    estimated_credits=800,
                    confirmed_at=datetime(2026, 7, 23, 12, 0),
                ),
            ]
        )
    yield GenerationHarness(
        GenerationService(session_factory, FakeSessions()), session_factory
    )
    await engine.dispose()
