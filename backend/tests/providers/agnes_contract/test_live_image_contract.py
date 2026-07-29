from io import BytesIO
import os
from uuid import UUID

from PIL import Image
import pytest

from app.core.database import DatabaseManager
from app.models import AiModel, AiProvider, ProviderCredential
from app.providers.agnes import AgnesAdapter, ImageGenerationRequest
from app.services.media.images.validation import (
    image_data_uri,
    validate_image_bytes,
)
from app.services.provider_security import CredentialCipher
from app.settings.config import Settings


RUN_LIVE = os.getenv("OFFICE_AI_RUN_REAL_AGNES_IMAGE_CONTRACT") == "1"
pytestmark = pytest.mark.skipif(
    not RUN_LIVE,
    reason=(
        "真实 Agnes Image Contract 未显式 opt-in；仅报告 Mock 通过，"
        "不读取本地 .env 或 Credential"
    ),
)


async def _runtime_image_client():
    credential_selector = os.getenv("OFFICE_AI_AGNES_IMAGE_CONTRACT_CREDENTIAL_ID")
    model_selector = os.getenv("OFFICE_AI_AGNES_IMAGE_CONTRACT_MODEL_ID")
    if not credential_selector or not model_selector:
        pytest.fail("缺少 Agnes Image Contract selector")
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
                or model.status != "active"
                or model.model_code != "agnes-image-2.1-flash"
                or model.capabilities.get("image_generation") is not True
            ):
                pytest.fail("选定 Agnes Image Credential/Model 未发布")
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


async def test_real_agnes_synthetic_text_to_image_contract() -> None:
    database, adapter, key, model = await _runtime_image_client()
    try:
        result = await adapter.create_image(
            api_key=key,
            request=ImageGenerationRequest(
                model=model.model_code,
                prompt=(
                    "Synthetic abstract blue business trend illustration, "
                    "no text, no logo, no people"
                ),
                size="2K",
                ratio="16:9",
                input_images=(),
                timeout_seconds=360,
                trace_id="real-agnes-image-text-contract",
            ),
        )
    finally:
        await database.close()
    image = validate_image_bytes(
        result.image_bytes,
        max_bytes=20 * 1024 * 1024,
        max_decoded_bytes=128 * 1024 * 1024,
    )
    assert image.width > image.height
    assert result.provider_request_id


async def test_real_agnes_synthetic_data_uri_contract() -> None:
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=(24, 72, 120)).save(buffer, "PNG")
    source = validate_image_bytes(
        buffer.getvalue(),
        max_bytes=1024,
        max_decoded_bytes=1024,
    )
    database, adapter, key, model = await _runtime_image_client()
    try:
        result = await adapter.create_image(
            api_key=key,
            request=ImageGenerationRequest(
                model=model.model_code,
                prompt="Preserve the synthetic blue square, no text and no logo",
                size="1K",
                ratio="1:1",
                input_images=(image_data_uri(source),),
                timeout_seconds=360,
                trace_id="real-agnes-image-data-uri-contract",
            ),
        )
    finally:
        await database.close()
    image = validate_image_bytes(
        result.image_bytes,
        max_bytes=20 * 1024 * 1024,
        max_decoded_bytes=128 * 1024 * 1024,
    )
    assert image.width >= 1
    assert image.height >= 1
    assert result.provider_request_id
