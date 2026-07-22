from app.settings.config import Settings
from pydantic import ValidationError
import pytest


def test_auth_secrets_have_no_source_default_and_ttls_are_configurable() -> None:
    settings = Settings(
        OFFICE_AI_SESSION_SECRET="runtime-session-secret-with-enough-entropy",
        OFFICE_AI_ACCESS_TOKEN_TTL_SECONDS=600,
        OFFICE_AI_REFRESH_TOKEN_TTL_SECONDS=1200,
        OFFICE_AI_BOOTSTRAP_ADMIN_PHONE="13800138000",
        OFFICE_AI_BOOTSTRAP_ADMIN_PASSWORD="runtime-admin-password",
    )

    assert settings.session_secret is not None
    assert settings.session_secret.get_secret_value() == (
        "runtime-session-secret-with-enough-entropy"
    )
    assert settings.access_token_ttl_seconds == 600
    assert settings.refresh_token_ttl_seconds == 1200
    assert settings.bootstrap_admin_phone == "13800138000"
    assert settings.bootstrap_admin_password is not None
    assert "runtime-admin-password" not in repr(settings)


def test_auth_secrets_are_absent_when_environment_does_not_provide_them() -> None:
    settings = Settings()

    assert settings.session_secret is None
    assert settings.bootstrap_admin_phone is None
    assert settings.bootstrap_admin_password is None


def test_empty_compose_secrets_are_treated_as_unconfigured() -> None:
    settings = Settings(
        OFFICE_AI_SESSION_SECRET="",
        OFFICE_AI_BOOTSTRAP_ADMIN_PHONE="",
        OFFICE_AI_BOOTSTRAP_ADMIN_PASSWORD="",
    )

    assert settings.session_secret is None
    assert settings.bootstrap_admin_phone is None
    assert settings.bootstrap_admin_password is None


def test_short_session_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(OFFICE_AI_SESSION_SECRET="too-short")
