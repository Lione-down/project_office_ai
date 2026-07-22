from app.settings.config import Settings


def test_settings_builds_internal_connection_targets_without_exposing_secrets() -> None:
    settings = Settings(
        OFFICE_AI_ENV="test",
        OFFICE_AI_MYSQL_DATABASE="office_ai_test",
        OFFICE_AI_MYSQL_USER="office_ai",
        OFFICE_AI_MYSQL_PASSWORD="do-not-log-this",
        OFFICE_AI_DATABASE_HOST="mysql",
        OFFICE_AI_REDIS_URL="redis://redis:6379/0",
    )

    assert settings.database_url.get_secret_value() == (
        "mysql+aiomysql://office_ai:do-not-log-this@mysql:3306/office_ai_test"
    )
    assert "do-not-log-this" not in repr(settings)
    assert "redis://redis:6379/0" not in repr(settings)


def test_settings_accepts_an_explicit_database_url_for_test_injection() -> None:
    settings = Settings(
        OFFICE_AI_DATABASE_URL="sqlite+aiosqlite:///:memory:",
        OFFICE_AI_REDIS_URL="redis://redis:6379/0",
    )

    assert settings.database_url.get_secret_value() == "sqlite+aiosqlite:///:memory:"
