from datetime import UTC, datetime
from uuid import UUID

from httpx import ASGITransport, AsyncClient

from app.core.application import AuthServices, create_app
from app.services.admin_contracts import (
    AdminAssetSummary,
    AdminUserSummary,
    AuditLogSummary,
    CreditAdjustmentResult,
)
from app.settings.config import Settings
from tests.auth.test_api import FakeRegistration, FakeSessions, ReadyDependencies


USER_ID = UUID("019f0000-0000-7000-8000-000000000921")
ASSET_ID = UUID("019f0000-0000-7000-8000-000000000922")
PROJECT_ID = UUID("019f0000-0000-7000-8000-000000000923")
LEDGER_ID = UUID("019f0000-0000-7000-8000-000000000924")
AUDIT_ID = UUID("019f0000-0000-7000-8000-000000000925")


class FakeAdminService:
    def __init__(self) -> None:
        self.status_payload: dict | None = None

    async def list_users(self, _access_token: str):
        return [
            AdminUserSummary(
                USER_ID,
                "+86 138****8001",
                "user",
                "active",
                100,
                False,
                datetime(2026, 7, 24, tzinfo=UTC),
            )
        ]

    async def change_user_status(self, **kwargs) -> None:
        self.status_payload = kwargs

    async def reset_password(self, **_kwargs) -> None:
        return None

    async def list_assets(self, _access_token: str):
        return [
            AdminAssetSummary(
                ASSET_ID,
                USER_ID,
                PROJECT_ID,
                "report.xlsx",
                "spreadsheet",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                123,
                "a" * 64,
                "ready",
                datetime(2026, 7, 24, tzinfo=UTC),
            )
        ]

    async def adjust_credits(self, **_kwargs):
        return CreditAdjustmentResult(LEDGER_ID, USER_ID, 25, 125)

    async def list_audit_logs(self, _access_token: str):
        return [
            AuditLogSummary(
                AUDIT_ID,
                USER_ID,
                "credit.adjusted",
                "user",
                USER_ID,
                "203.0.113.0/24",
                "pytest-admin-browser",
                "活动补发",
                "success",
                {"amount": 25},
                "trace-admin-api",
                datetime(2026, 7, 24, tzinfo=UTC),
            )
        ]


def build_app(service: FakeAdminService):
    return create_app(
        settings=Settings(
            OFFICE_AI_SESSION_SECRET="test-session-secret-with-enough-entropy"
        ),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(
            registration=FakeRegistration(), sessions=FakeSessions()
        ),
        admin_services=service,
    )


async def test_admin_management_http_contract_uses_json_reauth_and_safe_summaries() -> (
    None
):
    service = FakeAdminService()
    headers = {"Authorization": "Bearer access-token"}
    async with AsyncClient(
        transport=ASGITransport(app=build_app(service)), base_url="http://test"
    ) as client:
        users = await client.get("/api/v1/admin/users", headers=headers)
        assets = await client.get("/api/v1/admin/assets", headers=headers)
        status = await client.post(
            f"/api/v1/admin/users/{USER_ID}/status",
            headers=headers,
            json={
                "status": "suspended",
                "current_password": "admin-current-password",
                "reason": "风险复核",
            },
        )
        credits = await client.post(
            "/api/v1/admin/credits/adjustments",
            headers={**headers, "Idempotency-Key": "adjustment-1"},
            json={
                "user_id": str(USER_ID),
                "amount": 25,
                "current_password": "admin-current-password",
                "reason": "活动补发",
            },
        )
        audits = await client.get("/api/v1/admin/audit-logs", headers=headers)

    assert users.status_code == 200
    assert users.json()[0]["masked_phone"] == "+86 138****8001"
    assert assets.status_code == 200
    assert "storage_key" not in assets.text
    assert status.status_code == 204
    assert service.status_payload is not None
    assert service.status_payload["current_password"] == "admin-current-password"
    assert credits.status_code == 201
    assert audits.json()[0]["context"] == {"amount": 25}
    assert audits.json()[0]["ip_address"] == "203.0.113.0/24"


async def test_admin_asset_preview_is_post_only_to_keep_reauth_out_of_url() -> None:
    service = FakeAdminService()
    headers = {"Authorization": "Bearer access-token"}
    async with AsyncClient(
        transport=ASGITransport(app=build_app(service)), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/api/v1/admin/assets/{ASSET_ID}/preview",
            headers=headers,
            params={"current_password": "must-not-be-in-url", "reason": "bad"},
        )
    assert response.status_code == 405
