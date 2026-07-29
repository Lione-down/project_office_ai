import asyncio
import os
from uuid import UUID

import pytest

from app.core.database import DatabaseManager
from app.models import AiModel, AiProvider, ProviderCredential
from app.providers.agnes import AgnesAdapter, VideoGenerationRequest
from app.services.provider_security import CredentialCipher
from app.settings.config import Settings


RUN_LIVE = os.getenv("OFFICE_AI_RUN_REAL_AGNES_VIDEO_CONTRACT") == "1"
pytestmark = pytest.mark.skipif(
    not RUN_LIVE,
    reason=(
        "真实 Agnes Video Contract 未显式 opt-in；仅报告 Mock 通过，"
        "不读取本地 .env 或 Credential"
    ),
)


async def _runtime_video_client():
    credential_selector = os.getenv("OFFICE_AI_AGNES_VIDEO_CONTRACT_CREDENTIAL_ID")
    model_selector = os.getenv("OFFICE_AI_AGNES_VIDEO_CONTRACT_MODEL_ID")
    if not credential_selector or not model_selector:
        pytest.fail("缺少 Agnes Video Contract selector")
    settings = Settings()
    if settings.master_key is None:
        pytest.fail("缺少 runtime OFFICE_AI_MASTER_KEY")
    database = DatabaseManager(settings.database_url)
    try:
        async with database.session_factory() as session:
            credential = await session.get(
                ProviderCredential,
                UUID(credential_selector),
            )
            model = await session.get(AiModel, UUID(model_selector))
            provider = (
                await session.get(AiProvider, credential.provider_id)
                if credential is not None
                else None
            )
            if (
                credential is None
                or credential.status != "active"
                or provider is None
                or provider.vendor != "agnes"
                or model is None
                or model.credential_id != credential.id
                or model.status not in {"active", "published"}
                or model.model_code != "agnes-video-v2.0"
                or model.capabilities.get("video_generation") is not True
            ):
                pytest.fail("选定 Agnes Video Credential/Model 未发布")
            key = CredentialCipher(settings.master_key).decrypt(
                credential.encrypted_key
            )
            adapter = AgnesAdapter(
                configuration={
                    **provider.config,
                    "base_url": provider.base_url,
                    "timeout_seconds": provider.default_timeout_seconds,
                }
            )
            return database, adapter, key, model
    except Exception:
        await database.close()
        raise


async def test_real_agnes_synthetic_text_to_video_contract() -> None:
    database, adapter, key, model = await _runtime_video_client()
    try:
        submitted = await adapter.create_video(
            api_key=key,
            request=VideoGenerationRequest(
                model=model.model_code,
                prompt=(
                    "Synthetic blue geometric shapes moving slowly on a neutral "
                    "background, no text, no logo, no people"
                ),
                width=1152,
                height=768,
                num_frames=81,
                frame_rate=24,
                negative_prompt="text, logo, watermark, people",
                timeout_seconds=120,
                trace_id="real-agnes-video-text-contract",
            ),
        )
        result = submitted
        for _attempt in range(120):
            if result.status in {"completed", "failed"}:
                break
            await asyncio.sleep(max(5, result.retry_after_seconds or 0))
            result = await adapter.get_video(
                api_key=key,
                model=model.model_code,
                video_id=submitted.video_id,
                timeout_seconds=120,
                trace_id="real-agnes-video-poll-contract",
            )
    finally:
        await database.close()
    assert result.status == "completed"
    assert result.result_url is not None
    assert result.result_url.startswith("https://")
    assert result.video_id == submitted.video_id
    assert result.provider_request_id
