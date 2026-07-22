from base64 import urlsafe_b64encode

import pytest
from sqlalchemy import func, select

from app.models.ai_providers import AiProvider
from app.models.audit_logs import AuditLog
from app.models.provider_credentials import ProviderCredential
from app.services.auth_security import PasswordService
from app.services.provider_admin import (
    AuditContext,
    ProviderAdminService,
    ProviderOperationError,
)
from app.services.provider_security import CredentialCipher
from tests.auth.test_sessions import build_service, seed_user


def build_provider_admin_service(
    session_factory, adapter_factory=None
) -> ProviderAdminService:
    sessions = build_service(session_factory)
    cipher = CredentialCipher(
        urlsafe_b64encode(b"provider-test-master-key-32bytes").decode()
    )
    return ProviderAdminService(
        session_factory,
        sessions,
        PasswordService(),
        cipher,
        adapter_factory=adapter_factory,
    )


async def login_admin(session_factory):
    passwords = PasswordService()
    admin = await seed_user(
        session_factory,
        passwords,
        phone="13900139000",
        password="admin-correct-horse-battery-staple",
        role="admin",
    )
    tokens = await build_service(session_factory).login(
        admin.phone_number,
        "admin-correct-horse-battery-staple",
        "admin-ip",
        None,
        "admin-ip",
    )
    return admin, tokens.access_token


async def seed_provider(session_factory) -> AiProvider:
    provider = AiProvider(
        vendor="agnes",
        display_name="Agnes",
        protocol="openai_chat_completions",
        base_url="https://apihub.agnes-ai.com/v1",
        status="active",
        default_timeout_seconds=120,
        config={},
    )
    async with session_factory() as session, session.begin():
        session.add(provider)
    return provider


async def test_admin_creates_masked_encrypted_credential(session_factory) -> None:
    admin, access_token = await login_admin(session_factory)
    provider = await seed_provider(session_factory)
    service = build_provider_admin_service(session_factory)
    plaintext = "agnes-key-never-persist-1234"

    created = await service.create_credential(
        access_token=access_token,
        provider_id=provider.id,
        name="Primary",
        api_key=plaintext,
        rpm_limit=30,
        tpm_limit=100_000,
        max_concurrency=2,
        rotation_source="initial",
    )

    async with session_factory() as session:
        stored = await session.scalar(select(ProviderCredential))

    assert created.credential_id == stored.id
    assert created.masked_key == "****1234"
    assert not hasattr(created, "api_key")
    assert plaintext not in stored.encrypted_key
    assert stored.key_fingerprint != plaintext
    assert stored.created_by_user_id == admin.id


async def test_same_key_cannot_be_created_twice_for_one_provider(
    session_factory,
) -> None:
    _, access_token = await login_admin(session_factory)
    provider = await seed_provider(session_factory)
    service = build_provider_admin_service(session_factory)
    values = {
        "access_token": access_token,
        "provider_id": provider.id,
        "name": "Primary",
        "api_key": "duplicate-agnes-key-1234",
        "rpm_limit": 30,
        "tpm_limit": 100_000,
        "max_concurrency": 2,
        "rotation_source": "initial",
    }
    await service.create_credential(**values)

    with pytest.raises(ProviderOperationError) as error:
        await service.create_credential(**values)

    async with session_factory() as session:
        count = await session.scalar(select(func.count(ProviderCredential.id)))

    assert error.value.error_code == "credential_duplicate"
    assert error.value.status_code == 409
    assert count == 1


async def test_empty_credential_key_is_rejected_by_service(session_factory) -> None:
    _, access_token = await login_admin(session_factory)
    provider = await seed_provider(session_factory)
    service = build_provider_admin_service(session_factory)

    with pytest.raises(ProviderOperationError) as error:
        await service.create_credential(
            access_token=access_token,
            provider_id=provider.id,
            name="Invalid",
            api_key="  ",
            rpm_limit=30,
            tpm_limit=100_000,
            max_concurrency=2,
            rotation_source="initial",
        )

    assert error.value.error_code == "credential_key_invalid"


async def test_non_admin_cannot_create_provider_credential(session_factory) -> None:
    passwords = PasswordService()
    user = await seed_user(
        session_factory,
        passwords,
        phone="13800138000",
        password="user-correct-horse-battery-staple",
    )
    access_token = (
        await build_service(session_factory).login(
            user.phone_number,
            "user-correct-horse-battery-staple",
            "user-ip",
            None,
            "user-ip",
        )
    ).access_token
    provider = await seed_provider(session_factory)

    with pytest.raises(ProviderOperationError) as error:
        await build_provider_admin_service(session_factory).create_credential(
            access_token=access_token,
            provider_id=provider.id,
            name="Forbidden",
            api_key="never-store-this-key",
            rpm_limit=30,
            tpm_limit=100_000,
            max_concurrency=2,
            rotation_source="initial",
        )

    assert error.value.error_code == "admin_required"


async def test_reveal_requires_password_and_records_success_without_secret(
    session_factory,
) -> None:
    _, access_token = await login_admin(session_factory)
    provider = await seed_provider(session_factory)
    service = build_provider_admin_service(session_factory)
    plaintext = "agnes-key-reveal-only-9876"
    created = await service.create_credential(
        access_token=access_token,
        provider_id=provider.id,
        name="Reveal",
        api_key=plaintext,
        rpm_limit=30,
        tpm_limit=100_000,
        max_concurrency=2,
        rotation_source="initial",
    )

    revealed = await service.reveal_credential(
        access_token=access_token,
        credential_id=created.credential_id,
        current_password="admin-correct-horse-battery-staple",
        reason="credential rotation review",
        audit=AuditContext("127.0.0.1", "pytest", "trace-reveal-success"),
    )

    async with session_factory() as session:
        audit = await session.scalar(select(AuditLog))

    assert revealed.api_key == plaintext
    assert audit.action == "credential.revealed"
    assert audit.result == "success"
    assert plaintext not in str(audit.context)
    assert "fingerprint" not in str(audit.context).lower()


async def test_failed_reveal_is_audited(session_factory) -> None:
    _, access_token = await login_admin(session_factory)
    provider = await seed_provider(session_factory)
    service = build_provider_admin_service(session_factory)
    created = await service.create_credential(
        access_token=access_token,
        provider_id=provider.id,
        name="Reveal",
        api_key="agnes-key-never-audit-5555",
        rpm_limit=30,
        tpm_limit=100_000,
        max_concurrency=2,
        rotation_source="initial",
    )

    with pytest.raises(ProviderOperationError) as error:
        await service.reveal_credential(
            access_token=access_token,
            credential_id=created.credential_id,
            current_password="wrong-password-never-log",
            reason="credential rotation review",
            audit=AuditContext("127.0.0.1", "pytest", "trace-reveal-failed"),
        )

    async with session_factory() as session:
        audits = list(await session.scalars(select(AuditLog)))

    assert error.value.error_code == "reauthentication_failed"
    assert len(audits) == 1
    assert audits[0].result == "failed"
    assert "wrong-password-never-log" not in str(audits[0].context)


async def test_admin_registers_agnes_provider_and_bound_model(
    session_factory,
) -> None:
    _, access_token = await login_admin(session_factory)
    service = build_provider_admin_service(session_factory)
    provider = await service.create_provider(
        access_token=access_token,
        vendor="agnes",
        display_name="Agnes",
        protocol="openai_chat_completions",
        base_url="https://apihub.agnes-ai.com/v1",
        default_timeout_seconds=120,
        config={},
    )
    credential = await service.create_credential(
        access_token=access_token,
        provider_id=provider.provider_id,
        name="Primary",
        api_key="agnes-model-bound-key-2026",
        rpm_limit=30,
        tpm_limit=100_000,
        max_concurrency=2,
        rotation_source="initial",
    )

    model = await service.create_model(
        access_token=access_token,
        provider_id=provider.provider_id,
        credential_id=credential.credential_id,
        model_code="agnes-2.0-flash",
        display_name="Agnes 2.0 Flash",
        capabilities={"structured_output": True, "image_url": False},
        context_window=262_144,
        max_output_tokens=8_192,
        user_visible=True,
        is_recommended=True,
        credit_multiplier="1.0000",
        allowed_skills=["ppt.sales-business-review.v1"],
    )
    updated = await service.update_model(
        access_token=access_token,
        model_id=model.model_id,
        changes={"is_recommended": False, "status": "active"},
    )

    assert provider.vendor == "agnes"
    assert model.credential_id == credential.credential_id
    assert model.context_window == 262_144
    assert updated.is_recommended is False


async def test_agnes_provider_rejects_invalid_configuration(session_factory) -> None:
    _, access_token = await login_admin(session_factory)
    service = build_provider_admin_service(session_factory)

    with pytest.raises(ProviderOperationError) as error:
        await service.create_provider(
            access_token=access_token,
            vendor="agnes",
            display_name="Agnes",
            protocol="openai_chat_completions",
            base_url="http://insecure.example/v1",
            default_timeout_seconds=120,
            config={"context_window": 524_288},
        )

    assert error.value.error_code == "provider_configuration_invalid"


async def test_provider_config_rejects_secret_fields(session_factory) -> None:
    _, access_token = await login_admin(session_factory)
    service = build_provider_admin_service(session_factory)

    with pytest.raises(ProviderOperationError) as error:
        await service.create_provider(
            access_token=access_token,
            vendor="agnes",
            display_name="Agnes",
            protocol="openai_chat_completions",
            base_url="https://apihub.agnes-ai.com/v1",
            default_timeout_seconds=120,
            config={"api_key": "must-never-enter-provider-config"},
        )

    assert error.value.error_code == "provider_config_contains_secret"


async def test_model_rejects_credential_from_another_provider(
    session_factory,
) -> None:
    _, access_token = await login_admin(session_factory)
    service = build_provider_admin_service(session_factory)
    first = await service.create_provider(
        access_token=access_token,
        vendor="agnes",
        display_name="Agnes",
        protocol="openai_chat_completions",
        base_url="https://apihub.agnes-ai.com/v1",
        default_timeout_seconds=120,
        config={},
    )
    second = await service.create_provider(
        access_token=access_token,
        vendor="other",
        display_name="Other",
        protocol="openai_chat_completions",
        base_url="https://example.invalid/v1",
        default_timeout_seconds=120,
        config={},
    )
    credential = await service.create_credential(
        access_token=access_token,
        provider_id=first.provider_id,
        name="Primary",
        api_key="agnes-provider-only-key",
        rpm_limit=30,
        tpm_limit=100_000,
        max_concurrency=2,
        rotation_source="initial",
    )

    with pytest.raises(ProviderOperationError) as error:
        await service.create_model(
            access_token=access_token,
            provider_id=second.provider_id,
            credential_id=credential.credential_id,
            model_code="wrong-binding",
            display_name="Wrong",
            capabilities={},
            context_window=262_144,
            max_output_tokens=8_192,
            user_visible=True,
            is_recommended=False,
            credit_multiplier="1.0000",
            allowed_skills=[],
        )

    assert error.value.error_code == "credential_provider_mismatch"


async def test_user_lists_only_active_visible_models(session_factory) -> None:
    _, access_token = await login_admin(session_factory)
    service = build_provider_admin_service(session_factory)
    provider = await service.create_provider(
        access_token=access_token,
        vendor="agnes",
        display_name="Agnes",
        protocol="openai_chat_completions",
        base_url="https://apihub.agnes-ai.com/v1",
        default_timeout_seconds=120,
        config={},
    )
    credential = await service.create_credential(
        access_token=access_token,
        provider_id=provider.provider_id,
        name="Primary",
        api_key="agnes-visible-model-key",
        rpm_limit=30,
        tpm_limit=100_000,
        max_concurrency=2,
        rotation_source="initial",
    )
    visible = await service.create_model(
        access_token=access_token,
        provider_id=provider.provider_id,
        credential_id=credential.credential_id,
        model_code="agnes-2.0-flash",
        display_name="Agnes 2.0 Flash",
        capabilities={"structured_output": True},
        context_window=262_144,
        max_output_tokens=8_192,
        user_visible=True,
        is_recommended=True,
        credit_multiplier="1.0000",
        allowed_skills=[],
    )
    await service.create_model(
        access_token=access_token,
        provider_id=provider.provider_id,
        credential_id=credential.credential_id,
        model_code="hidden-model",
        display_name="Hidden",
        capabilities={},
        context_window=32_768,
        max_output_tokens=4_096,
        user_visible=False,
        is_recommended=False,
        credit_multiplier="1.0000",
        allowed_skills=[],
    )

    listed = await service.list_visible_models(access_token)

    assert [item.model_id for item in listed] == [visible.model_id]
    assert listed[0].credential_id == credential.credential_id
