from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import (
    AiModel,
    AiProvider,
    Base,
    Brief,
    FileAsset,
    Project,
    ProviderCredential,
    Skill,
    User,
)
from app.services.auth_sessions import CurrentUser
from app.services.evidence.contracts import EngineVersion, EvidenceManifest
from app.services.evidence.store import EvidenceManifestStore
from app.services.preflight.service import BriefWorkflowService
from app.skills.catalog import ALPHA_SKILLS
from tests.briefs.helpers import (
    ASSET_ID,
    ASSET_VERSION,
    BRIEF_GROUP_ID,
    CREDENTIAL_ID,
    MODEL_ID,
    PROJECT_ID,
    PROVIDER_ID,
    USER_ID,
    source_evidence,
    valid_brief_payload,
)


BRIEF_ID = UUID("019f4000-0000-7000-8000-000000000030")
OTHER_USER_ID = UUID("019f4000-0000-7000-8000-000000000031")


class FakeSessions:
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


@dataclass
class PreflightHarness:
    service: BriefWorkflowService
    session_factory: async_sessionmaker[AsyncSession]
    manifest_store: EvidenceManifestStore


@pytest_asyncio.fixture
async def preflight_harness(tmp_path: Path) -> AsyncIterator[PreflightHarness]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    manifest_store = EvidenceManifestStore(tmp_path, max_output_bytes=64 * 1024)
    manifest = EvidenceManifest(
        schema_version="evidence-manifest.v1",
        manifest_id=f"m-{'4' * 64}",
        asset_id=ASSET_ID,
        asset_version=ASSET_VERSION,
        generated_at=datetime(2026, 7, 23, 23, 0, tzinfo=UTC),
        generator=EngineVersion(name="office-ai-evidence", version="1.0.0"),
        source_parser=EngineVersion(name="xlsx-safe", version="1.0.0"),
        evidence=(source_evidence(),),
    )
    stored = manifest_store.write(USER_ID, ASSET_ID, manifest)
    content = valid_brief_payload()
    source_snapshot = {
        key: content[key]
        for key in (
            "module",
            "goal",
            "audience",
            "source_asset_versions",
            "term_library_versions",
            "selected_skills",
            "selected_model",
            "must_include",
            "must_exclude",
        )
    }
    content_checksum = sha256(
        json.dumps(
            content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    async with session_factory() as session, session.begin():
        session.add_all(
            [
                User(
                    id=USER_ID,
                    phone_number="13800000000",
                    password_hash="test-hash",
                    credit_balance=10_000,
                ),
                User(
                    id=OTHER_USER_ID,
                    phone_number="13900000000",
                    password_hash="test-hash",
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
                        "image_input": False,
                    },
                    context_window=4096,
                    max_output_tokens=512,
                    user_visible=True,
                    is_recommended=True,
                    credit_multiplier="1.0000",
                    allowed_skills=[skill.skill_code for skill in ALPHA_SKILLS],
                    status="active",
                ),
                FileAsset(
                    id=ASSET_ID,
                    user_id=USER_ID,
                    project_id=PROJECT_ID,
                    original_filename="sales.xlsx",
                    file_category="spreadsheet",
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    byte_size=128,
                    sha256=ASSET_VERSION.removeprefix("sha256:"),
                    storage_provider="local",
                    storage_key=f"users/{USER_ID}/quarantine/{ASSET_ID}/original.xlsx",
                    processing_status="ready",
                    manifest_key=stored.storage_key,
                    manifest_status="valid",
                    manifest_sha256=stored.sha256,
                    manifest_schema_version="evidence-manifest.v1",
                    evidence_engine_version="1.0.0",
                    evidence_warning_count=0,
                    evidence_blocker_count=0,
                ),
                Brief(
                    id=BRIEF_ID,
                    brief_group_id=BRIEF_GROUP_ID,
                    revision=1,
                    user_id=USER_ID,
                    project_id=PROJECT_ID,
                    selected_model_id=MODEL_ID,
                    source_snapshot=source_snapshot,
                    content=content,
                    content_checksum=content_checksum,
                    status="draft",
                ),
                *[
                    Skill(
                        skill_code=skill.skill_code,
                        version=skill.version,
                        kind=skill.kind,
                        display_name=skill.display_name,
                        description=skill.description,
                        output_kind=skill.output_kind,
                        input_schema=skill.input_schema,
                        output_schema=skill.output_schema,
                        workflow=skill.workflow,
                        capability_requirements=skill.capability_requirements,
                        status=skill.status,
                        checksum=skill.checksum,
                    )
                    for skill in ALPHA_SKILLS
                ],
            ]
        )
    service = BriefWorkflowService(session_factory, FakeSessions(), manifest_store)
    yield PreflightHarness(service, session_factory, manifest_store)
    await engine.dispose()
