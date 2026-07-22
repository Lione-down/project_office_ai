from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.audit_logs import AuditLog
from app.models.provider_credentials import ProviderCredential


def test_provider_registry_models_are_part_of_metadata() -> None:
    assert {
        "ai_providers",
        "provider_credentials",
        "ai_models",
        "audit_logs",
    } <= set(AiProvider.metadata.tables)


async def test_each_credential_has_one_id_and_provider_fingerprint_is_unique(
    session_factory,
) -> None:
    provider = AiProvider(
        vendor="agnes",
        display_name="Agnes",
        protocol="openai_chat_completions",
        base_url="https://apihub.agnes-ai.com/v1",
        status="active",
        default_timeout_seconds=120,
        config={},
    )
    first = ProviderCredential(
        provider_id=provider.id,
        name="Primary",
        encrypted_key="encrypted:first",
        key_fingerprint="a" * 64,
        status="active",
        rpm_limit=30,
        tpm_limit=100_000,
        max_concurrency=2,
        rotation_source="initial",
    )
    duplicate = ProviderCredential(
        provider_id=provider.id,
        name="Duplicate",
        encrypted_key="encrypted:second",
        key_fingerprint="a" * 64,
        status="active",
        rpm_limit=30,
        tpm_limit=100_000,
        max_concurrency=2,
        rotation_source="initial",
    )

    assert first.id != duplicate.id

    async with session_factory() as session:
        session.add_all((provider, first))
        await session.commit()
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_model_is_explicitly_bound_to_provider_credential(
    session_factory,
) -> None:
    provider = AiProvider(
        vendor="agnes",
        display_name="Agnes",
        protocol="openai_chat_completions",
        base_url="https://apihub.agnes-ai.com/v1",
        status="active",
        default_timeout_seconds=120,
        config={},
    )
    credential = ProviderCredential(
        provider_id=provider.id,
        name="Primary",
        encrypted_key="encrypted:value",
        key_fingerprint="b" * 64,
        status="active",
        rpm_limit=30,
        tpm_limit=100_000,
        max_concurrency=2,
        rotation_source="initial",
    )
    model = AiModel(
        provider_id=provider.id,
        credential_id=credential.id,
        model_code="agnes-2.0-flash",
        display_name="Agnes 2.0 Flash",
        capabilities={"structured_output": True, "image_url": False},
        context_window=262_144,
        max_output_tokens=8_192,
        user_visible=True,
        is_recommended=True,
        credit_multiplier=Decimal("1.0000"),
        allowed_skills=["ppt.sales-business-review.v1"],
        status="active",
    )
    audit = AuditLog(
        action="credential.created",
        target_type="provider_credential",
        target_id=credential.id,
        reason="initial setup",
        result="success",
        context={"credential_name": "Primary"},
        trace_id="trace-provider-model",
    )

    async with session_factory() as session, session.begin():
        session.add_all((provider, credential, model, audit))

    assert model.credential_id == credential.id
    assert model.provider_id == provider.id
    assert audit.context == {"credential_name": "Primary"}
