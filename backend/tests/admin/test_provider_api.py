from decimal import Decimal
from uuid import UUID

from httpx import ASGITransport, AsyncClient

from app.core.application import AuthServices, create_app
from app.services.provider_admin import (
    CreatedCredential,
    CredentialSummary,
    CredentialTestResult,
    ModelSummary,
    ProviderSummary,
    RevealedCredential,
)
from app.settings.config import Settings
from tests.auth.test_api import FakeRegistration, FakeSessions, ReadyDependencies


PROVIDER_ID = UUID("019f0000-0000-7000-8000-000000000101")
CREDENTIAL_ID = UUID("019f0000-0000-7000-8000-000000000102")
MODEL_ID = UUID("019f0000-0000-7000-8000-000000000103")


def provider_summary() -> ProviderSummary:
    return ProviderSummary(
        provider_id=PROVIDER_ID,
        vendor="agnes",
        display_name="Agnes",
        protocol="openai_chat_completions",
        base_url="https://apihub.agnes-ai.com/v1",
        status="active",
        default_timeout_seconds=120,
        config={},
    )


def model_summary() -> ModelSummary:
    return ModelSummary(
        model_id=MODEL_ID,
        provider_id=PROVIDER_ID,
        credential_id=CREDENTIAL_ID,
        model_code="agnes-2.0-flash",
        display_name="Agnes 2.0 Flash",
        capabilities={"structured_output": True},
        context_window=262_144,
        max_output_tokens=8_192,
        user_visible=True,
        is_recommended=True,
        credit_multiplier=Decimal("1.0000"),
        allowed_skills=["ppt.sales-business-review.v1"],
        status="active",
    )


class FakeProviderService:
    def __init__(self) -> None:
        self.seen_key: str | None = None
        self.provider_changes: dict | None = None
        self.model_changes: dict | None = None

    async def create_provider(self, **_kwargs) -> ProviderSummary:
        return provider_summary()

    async def update_provider(self, **kwargs) -> ProviderSummary:
        self.provider_changes = kwargs["changes"]
        return provider_summary()

    async def create_credential(self, **kwargs) -> CreatedCredential:
        self.seen_key = kwargs["api_key"]
        return CreatedCredential(
            credential_id=CREDENTIAL_ID,
            provider_id=PROVIDER_ID,
            name="Primary",
            masked_key="****1234",
            status="active",
            rpm_limit=30,
            tpm_limit=100_000,
            max_concurrency=2,
            rotation_source="initial",
        )

    async def update_credential(self, **_kwargs) -> CredentialSummary:
        return CredentialSummary(
            credential_id=CREDENTIAL_ID,
            provider_id=PROVIDER_ID,
            name="Standby",
            masked_key="********",
            status="inactive",
            rpm_limit=10,
            tpm_limit=100_000,
            max_concurrency=2,
            rotation_source="initial",
            last_test_status="healthy",
        )

    async def reveal_credential(self, **_kwargs) -> RevealedCredential:
        return RevealedCredential(CREDENTIAL_ID, "revealed-only-once-1234")

    async def test_credential(self, **_kwargs) -> CredentialTestResult:
        return CredentialTestResult(CREDENTIAL_ID, "healthy", False, False)

    async def create_model(self, **_kwargs) -> ModelSummary:
        return model_summary()

    async def update_model(self, **kwargs) -> ModelSummary:
        self.model_changes = kwargs["changes"]
        return model_summary()

    async def list_visible_models(self, _access_token: str) -> list[ModelSummary]:
        return [model_summary()]

    async def list_providers(self, _access_token: str) -> list[ProviderSummary]:
        return [provider_summary()]

    async def list_credentials(self, _access_token: str) -> list[CredentialSummary]:
        return [await self.update_credential()]

    async def list_models(self, _access_token: str) -> list[ModelSummary]:
        return [model_summary()]


def build_app(provider_service: FakeProviderService):
    return create_app(
        settings=Settings(
            OFFICE_AI_SESSION_SECRET="test-session-secret-with-enough-entropy"
        ),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(
            registration=FakeRegistration(), sessions=FakeSessions()
        ),
        provider_services=provider_service,
    )


async def test_admin_provider_credential_and_model_api_contract() -> None:
    service = FakeProviderService()
    headers = {"Authorization": "Bearer access-token"}
    async with AsyncClient(
        transport=ASGITransport(app=build_app(service)), base_url="http://test"
    ) as client:
        provider = await client.post(
            "/api/v1/admin/providers",
            headers=headers,
            json={
                "vendor": "agnes",
                "display_name": "Agnes",
                "protocol": "openai_chat_completions",
                "base_url": "https://apihub.agnes-ai.com/v1",
                "default_timeout_seconds": 120,
                "config": {},
            },
        )
        patched_provider = await client.patch(
            f"/api/v1/admin/providers/{PROVIDER_ID}",
            headers=headers,
            json={"status": "inactive"},
        )
        providers = await client.get("/api/v1/admin/providers", headers=headers)
        credential = await client.post(
            "/api/v1/admin/credentials",
            headers=headers,
            json={
                "provider_id": str(PROVIDER_ID),
                "name": "Primary",
                "api_key": "request-only-agnes-key-1234",
                "rpm_limit": 30,
                "tpm_limit": 100000,
                "max_concurrency": 2,
                "rotation_source": "initial",
            },
        )
        patched_credential = await client.patch(
            f"/api/v1/admin/credentials/{CREDENTIAL_ID}",
            headers=headers,
            json={"name": "Standby", "status": "inactive", "rpm_limit": 10},
        )
        credentials = await client.get("/api/v1/admin/credentials", headers=headers)
        tested = await client.post(
            f"/api/v1/admin/credentials/{CREDENTIAL_ID}/test",
            headers=headers,
            json={"reason": "validate Agnes access"},
        )
        revealed = await client.post(
            f"/api/v1/admin/credentials/{CREDENTIAL_ID}/reveal",
            headers=headers,
            json={
                "current_password": "admin-correct-horse-battery-staple",
                "reason": "credential rotation review",
            },
        )
        model = await client.post(
            "/api/v1/admin/models",
            headers=headers,
            json={
                "provider_id": str(PROVIDER_ID),
                "credential_id": str(CREDENTIAL_ID),
                "model_code": "agnes-2.0-flash",
                "display_name": "Agnes 2.0 Flash",
                "capabilities": {"structured_output": True},
                "context_window": 262144,
                "max_output_tokens": 8192,
                "user_visible": True,
                "is_recommended": True,
                "credit_multiplier": "1.0000",
                "allowed_skills": ["ppt.sales-business-review.v1"],
            },
        )
        patched_model = await client.patch(
            f"/api/v1/admin/models/{MODEL_ID}",
            headers=headers,
            json={"is_recommended": False},
        )
        admin_models = await client.get("/api/v1/admin/models", headers=headers)
        visible_models = await client.get("/api/v1/models", headers=headers)

    assert provider.status_code == 201
    assert patched_provider.status_code == 200
    assert service.provider_changes == {"status": "inactive"}
    assert providers.json()[0]["vendor"] == "agnes"
    assert credential.status_code == 201
    assert credential.json()["masked_key"] == "****1234"
    assert "api_key" not in credential.json()
    assert credential.headers["cache-control"] == "no-store"
    assert service.seen_key == "request-only-agnes-key-1234"
    assert patched_credential.json()["masked_key"] == "********"
    assert credentials.json()[0]["masked_key"] == "********"
    assert "api_key" not in credentials.json()[0]
    assert tested.json()["status"] == "healthy"
    assert revealed.json()["api_key"] == "revealed-only-once-1234"
    assert revealed.headers["cache-control"] == "no-store"
    assert model.status_code == 201
    assert patched_model.status_code == 200
    assert service.model_changes == {"is_recommended": False}
    assert admin_models.json()[0]["model_code"] == "agnes-2.0-flash"
    assert visible_models.json()[0]["model_code"] == "agnes-2.0-flash"
    assert "request-only-agnes-key-1234" not in credential.text


async def test_credential_api_rejects_empty_key() -> None:
    service = FakeProviderService()
    async with AsyncClient(
        transport=ASGITransport(app=build_app(service)), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/admin/credentials",
            headers={"Authorization": "Bearer access-token"},
            json={
                "provider_id": str(PROVIDER_ID),
                "name": "Invalid",
                "api_key": "",
                "rpm_limit": 30,
                "tpm_limit": 100000,
                "max_concurrency": 2,
                "rotation_source": "initial",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "validation_error"
    assert service.seen_key is None
