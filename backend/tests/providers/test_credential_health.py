import httpx
from sqlalchemy import select

from app.models.audit_logs import AuditLog
from app.models.provider_credentials import ProviderCredential
from app.providers.agnes import AgnesAdapter
from app.services.provider_admin import AuditContext
from app.services.provider_security import CredentialCipher
from tests.providers.test_provider_admin import (
    build_provider_admin_service,
    login_admin,
    seed_provider,
)


class HealthyAdapter:
    def __init__(self) -> None:
        self.seen_key: str | None = None

    async def test_authentication(self, api_key: str) -> bool:
        self.seen_key = api_key
        return True

    def classify_error(self, error: Exception):
        return AgnesAdapter().classify_error(error)


class FailingAdapter(HealthyAdapter):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    async def test_authentication(self, api_key: str) -> bool:
        self.seen_key = api_key
        raise self.error


async def create_testable_credential(session_factory, adapter):
    _, access_token = await login_admin(session_factory)
    provider = await seed_provider(session_factory)
    service = build_provider_admin_service(
        session_factory, adapter_factory=lambda _provider: adapter
    )
    created = await service.create_credential(
        access_token=access_token,
        provider_id=provider.id,
        name="Health Test",
        api_key="agnes-health-test-key-2468",
        rpm_limit=30,
        tpm_limit=100_000,
        max_concurrency=2,
        rotation_source="initial",
    )
    return access_token, service, created


async def test_credential_health_success_is_persisted_and_audited(
    session_factory,
) -> None:
    adapter = HealthyAdapter()
    access_token, service, created = await create_testable_credential(
        session_factory, adapter
    )

    result = await service.test_credential(
        access_token=access_token,
        credential_id=created.credential_id,
        reason="validate Agnes access",
        audit=AuditContext("127.0.0.1", "pytest", "trace-test-success"),
    )

    async with session_factory() as session:
        stored = await session.get(ProviderCredential, created.credential_id)
        audit = await session.scalar(select(AuditLog))

    assert adapter.seen_key == "agnes-health-test-key-2468"
    assert result.status == "healthy"
    assert not hasattr(result, "api_key")
    assert stored.last_test_status == "healthy"
    assert stored.last_tested_at is not None
    assert audit.action == "credential.tested"
    assert audit.result == "success"
    assert "agnes-health-test-key-2468" not in str(audit.context)


async def test_authentication_failure_disables_credential_and_audits_failure(
    session_factory,
) -> None:
    response = httpx.Response(
        401, request=httpx.Request("POST", "https://apihub.agnes-ai.com/v1")
    )
    adapter = FailingAdapter(
        httpx.HTTPStatusError(
            "unauthorized", request=response.request, response=response
        )
    )
    access_token, service, created = await create_testable_credential(
        session_factory, adapter
    )

    result = await service.test_credential(
        access_token=access_token,
        credential_id=created.credential_id,
        reason="validate Agnes access",
        audit=AuditContext("127.0.0.1", "pytest", "trace-test-failed"),
    )

    async with session_factory() as session:
        stored = await session.get(ProviderCredential, created.credential_id)
        audit = await session.scalar(select(AuditLog))

    assert result.status == "authentication"
    assert result.retryable is False
    assert stored.status == "suspended"
    assert stored.last_test_status == "authentication"
    assert audit.result == "failed"


async def test_admin_lists_registry_and_updates_only_credential_metadata(
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
        api_key="agnes-list-never-decrypt-key-8642",
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
        capabilities={},
        context_window=262_144,
        max_output_tokens=8_192,
        user_visible=False,
        is_recommended=False,
        credit_multiplier="1.0000",
        allowed_skills=[],
    )

    updated = await service.update_credential(
        access_token=access_token,
        credential_id=credential.credential_id,
        changes={"name": "Standby", "status": "inactive", "rpm_limit": 10},
    )
    providers = await service.list_providers(access_token)
    credentials = await service.list_credentials(access_token)
    models = await service.list_models(access_token)

    async with session_factory() as session:
        stored = await session.get(ProviderCredential, credential.credential_id)

    assert [item.provider_id for item in providers] == [provider.provider_id]
    assert [item.credential_id for item in credentials] == [credential.credential_id]
    assert credentials[0].masked_key == "********"
    assert not hasattr(credentials[0], "api_key")
    assert [item.model_id for item in models] == [model.model_id]
    assert updated.name == "Standby"
    assert stored.encrypted_key != "agnes-list-never-decrypt-key-8642"
    assert stored.key_fingerprint == CredentialCipher.fingerprint(
        "agnes-list-never-decrypt-key-8642"
    )
