import json
import os
from time import perf_counter
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.database import DatabaseManager
from app.models import AiModel, AiProvider, ProviderCredential
from app.providers.agnes import AgnesAdapter, ChatStreamRequest, ProviderUsage
from app.services.provider_security import CredentialCipher
from app.settings.config import Settings


MODEL_CODES = ("agnes-2.5-flash", "agnes-2.0-flash")
RUN_LIVE = os.getenv("OFFICE_AI_RUN_REAL_AGNES_CHAT_CONTRACT") == "1"
pytestmark = pytest.mark.skipif(
    not RUN_LIVE,
    reason=(
        "真实 Agnes Chat Contract 未显式 opt-in；仅报告 Mock 通过，不读取 Credential"
    ),
)


async def _runtime_contract():
    credential_selector = os.getenv("OFFICE_AI_AGNES_CHAT_CONTRACT_CREDENTIAL_ID")
    model_selectors = os.getenv("OFFICE_AI_AGNES_CHAT_CONTRACT_MODEL_IDS")
    if not credential_selector:
        pytest.fail("缺少 OFFICE_AI_AGNES_CHAT_CONTRACT_CREDENTIAL_ID selector")
    if not model_selectors:
        pytest.fail("缺少 OFFICE_AI_AGNES_CHAT_CONTRACT_MODEL_IDS selectors")
    try:
        model_ids = tuple(
            UUID(item.strip()) for item in model_selectors.split(",") if item.strip()
        )
    except ValueError:
        pytest.fail("OFFICE_AI_AGNES_CHAT_CONTRACT_MODEL_IDS 格式无效")
    if len(model_ids) != 2 or len(set(model_ids)) != 2:
        pytest.fail("必须显式选择两个不同的 Agnes Chat model ID")
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
            if credential is None or credential.status != "active":
                pytest.fail("选定 Agnes Credential 不存在或未启用")
            provider = await session.get(AiProvider, credential.provider_id)
            models = list(
                await session.scalars(
                    select(AiModel).where(
                        AiModel.credential_id == credential.id,
                        AiModel.id.in_(model_ids),
                        AiModel.model_code.in_(MODEL_CODES),
                        AiModel.status == "active",
                        AiModel.user_visible.is_(True),
                    )
                )
            )
            models_by_code = {model.model_code: model for model in models}
            if provider is None or provider.vendor != "agnes":
                pytest.fail("选定 Credential 不是 Agnes Provider")
            if set(models_by_code) != set(MODEL_CODES):
                pytest.fail("选定 Credential 未同时发布 Agnes 2.5/2.0 Chat 模型")
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
            return database, adapter, key, models_by_code
    except Exception:
        await database.close()
        raise


def _request(model_code: str, trace_suffix: str) -> ChatStreamRequest:
    return ChatStreamRequest(
        model=model_code,
        messages=[
            {
                "role": "system",
                "content": "Return only the final answer. Do not use tools.",
            },
            {
                "role": "user",
                "content": "Reply with exactly: SYNTHETIC_OK",
            },
        ],
        tools=[],
        timeout_seconds=120,
        max_output_tokens=32,
        trace_id=f"real-agnes-chat-{trace_suffix}",
        thinking_enabled=False,
    )


@pytest.mark.parametrize("model_code", MODEL_CODES)
async def test_real_agnes_chat_stream_contract(model_code: str) -> None:
    database, adapter, key, models = await _runtime_contract()
    assert models[model_code].capabilities.get("chat_stream") is True
    content = ""
    usage = ProviderUsage()
    finish_reason = None
    started = perf_counter()
    try:
        async for chunk in adapter.stream_chat_completion(
            api_key=key,
            request=_request(model_code, f"{model_code}-complete"),
        ):
            content += chunk.content_delta
            if chunk.usage.total_tokens:
                usage = chunk.usage
            finish_reason = chunk.finish_reason or finish_reason
    finally:
        await database.close()

    latency_ms = int((perf_counter() - started) * 1000)
    assert "SYNTHETIC_OK" in content
    assert finish_reason
    print(
        json.dumps(
            {
                "model": model_code,
                "status": "completed",
                "latency_ms": latency_ms,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            },
            separators=(",", ":"),
        )
    )


@pytest.mark.parametrize("model_code", MODEL_CODES)
async def test_real_agnes_chat_stream_can_be_closed(model_code: str) -> None:
    database, adapter, key, _models = await _runtime_contract()
    iterator = adapter.stream_chat_completion(
        api_key=key,
        request=_request(model_code, f"{model_code}-stop"),
    ).__aiter__()
    started = perf_counter()
    received_delta = False
    try:
        for _ in range(64):
            chunk = await anext(iterator)
            if chunk.content_delta:
                received_delta = True
                break
        await iterator.aclose()
    finally:
        await database.close()

    latency_ms = int((perf_counter() - started) * 1000)
    assert received_delta
    print(
        json.dumps(
            {
                "model": model_code,
                "status": "closed_after_delta",
                "latency_ms": latency_ms,
            },
            separators=(",", ":"),
        )
    )
