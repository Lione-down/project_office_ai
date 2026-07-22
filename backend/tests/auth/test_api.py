from uuid import UUID

from httpx import ASGITransport, AsyncClient

from app.core.application import AuthServices, create_app
from app.services.auth_registration import AuthOperationError, RegisteredUser
from app.services.auth_sessions import CurrentUser, TokenPair
from app.settings.config import Settings


USER_ID = UUID("019f0000-0000-7000-8000-000000000001")
REFRESH_TOKEN = "refresh-token-that-is-long-enough-12345"
ROTATED_REFRESH_TOKEN = "rotated-refresh-token-that-is-long-enough"


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


class FakeRegistration:
    error: AuthOperationError | None = None

    async def register(self, **_kwargs) -> RegisteredUser:
        if self.error is not None:
            raise self.error
        return RegisteredUser(user_id=USER_ID)


class FakeSessions:
    async def login(self, **_kwargs) -> TokenPair:
        return TokenPair("access-token", REFRESH_TOKEN)

    async def refresh(self, **_kwargs) -> TokenPair:
        return TokenPair("rotated-access-token", ROTATED_REFRESH_TOKEN)

    async def logout(self, access_token: str) -> None:
        assert access_token == "access-token"

    async def authenticate_access(self, access_token: str) -> CurrentUser:
        assert access_token == "access-token"
        return CurrentUser(
            user_id=USER_ID,
            phone_country_code="+86",
            phone_number="13800138000",
            role="user",
            status="active",
            credit_balance=100,
            must_change_password=False,
        )

    async def change_password(self, **_kwargs) -> TokenPair:
        return TokenPair("new-access-token", "new-refresh-token")


def build_app(registration=None):
    return create_app(
        settings=Settings(
            OFFICE_AI_SESSION_SECRET="test-session-secret-with-enough-entropy"
        ),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(
            registration=registration or FakeRegistration(),
            sessions=FakeSessions(),
        ),
    )


async def test_auth_api_exposes_registration_login_refresh_logout_me_and_change() -> (
    None
):
    async with AsyncClient(
        transport=ASGITransport(app=build_app()), base_url="http://test"
    ) as client:
        registration = await client.post(
            "/api/v1/auth/register",
            json={
                "phone_number": "13800138000",
                "password": "correct-horse-battery-staple",
                "invite_code": "ALPHA-2026",
                "accepted_terms": True,
            },
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "phone_number": "13800138000",
                "password": "correct-horse-battery-staple",
            },
        )
        refresh = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": REFRESH_TOKEN}
        )
        me = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer access-token"}
        )
        changed = await client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": "Bearer access-token"},
            json={
                "current_password": "correct-horse-battery-staple",
                "new_password": "new-correct-horse-battery-staple",
            },
        )
        logout = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer access-token"},
        )

    assert registration.status_code == 201
    assert registration.json()["access_token"] == "access-token"
    assert login.status_code == 200
    assert refresh.json()["refresh_token"] == ROTATED_REFRESH_TOKEN
    assert me.json()["phone_number"] == "13800138000"
    assert changed.json()["access_token"] == "new-access-token"
    assert logout.status_code == 204
    assert registration.headers["cache-control"] == "no-store"
    assert login.headers["cache-control"] == "no-store"
    assert refresh.headers["cache-control"] == "no-store"
    assert changed.headers["cache-control"] == "no-store"


async def test_auth_api_returns_stable_error_without_echoing_sensitive_input() -> None:
    registration = FakeRegistration()
    registration.error = AuthOperationError(
        "phone_already_registered", "该手机号已注册", 409
    )
    async with AsyncClient(
        transport=ASGITransport(app=build_app(registration)), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "phone_number": "13800138000",
                "password": "never-echo-this-password",
                "invite_code": "NEVER-ECHO-THIS-CODE",
                "accepted_terms": True,
            },
        )

    assert response.status_code == 409
    assert response.json()["error"]["error_code"] == "phone_already_registered"
    assert "never-echo-this-password" not in response.text
    assert "NEVER-ECHO-THIS-CODE" not in response.text


async def test_registration_requires_china_phone_strong_password_and_terms() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=build_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "phone_number": "123",
                "password": "short",
                "invite_code": "ALPHA-2026",
                "accepted_terms": False,
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "validation_error"
    assert "short" not in response.text
