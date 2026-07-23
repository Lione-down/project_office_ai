from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.application import AuthServices, create_app
from app.models.credit_ledger import CreditLedger
from app.services.generation_contracts import GenerationServices
from app.settings.config import Settings
from tests.generation.conftest import BRIEF_ID


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


class Sessions:
    async def authenticate_access(self, access_token: str):
        return object()


async def test_generation_and_credit_endpoints_are_owner_scoped_and_idempotent(
    generation_harness,
) -> None:
    app = create_app(
        settings=Settings(),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=Sessions()),
        generation_services=GenerationServices(generation_harness.service),
    )
    headers = {
        "Authorization": "Bearer access-token",
        "Idempotency-Key": "api-generation-001",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/generations",
            headers=headers,
            json={"brief_id": str(BRIEF_ID)},
        )
        replay = await client.post(
            "/api/v1/generations",
            headers=headers,
            json={"brief_id": str(BRIEF_ID)},
        )
        detail = await client.get(
            f"/api/v1/generations/{created.json()['task_id']}",
            headers={"Authorization": "Bearer access-token"},
        )
        balance = await client.get(
            "/api/v1/credits/balance",
            headers={"Authorization": "Bearer access-token"},
        )
        ledger = await client.get(
            "/api/v1/credits/ledger",
            headers={"Authorization": "Bearer access-token"},
        )

    assert created.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert detail.status_code == 200
    assert detail.headers["cache-control"] == "private, no-store"
    assert balance.json() == {"balance": 4200}
    assert len(ledger.json()["entries"]) == 1
    assert "phone_number" not in str(ledger.json())

    async with generation_harness.session_factory() as session:
        entry = await session.scalar(select(CreditLedger))
    assert entry.description is None


async def test_generation_api_requires_valid_idempotency_key(
    generation_harness,
) -> None:
    app = create_app(
        settings=Settings(),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=Sessions()),
        generation_services=GenerationServices(generation_harness.service),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        missing = await client.post(
            "/api/v1/generations",
            headers={"Authorization": "Bearer access-token"},
            json={"brief_id": str(BRIEF_ID)},
        )
        unsafe = await client.post(
            "/api/v1/generations",
            headers={
                "Authorization": "Bearer access-token",
                "Idempotency-Key": " contains spaces ",
            },
            json={"brief_id": str(BRIEF_ID)},
        )

    assert missing.status_code == 422
    assert unsafe.status_code == 422
