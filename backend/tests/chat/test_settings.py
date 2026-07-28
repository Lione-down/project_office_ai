import pytest
from pydantic import ValidationError

from app.settings.config import Settings


def test_chat_settings_use_frozen_fail_closed_defaults() -> None:
    settings = Settings(
        OFFICE_AI_DATABASE_URL="sqlite+aiosqlite:///:memory:",
        OFFICE_AI_REDIS_URL="redis://redis:6379/0",
    )

    assert settings.chat_max_input_chars == 32768
    assert settings.chat_max_output_tokens == 8192
    assert settings.chat_stream_timeout_seconds == 180
    assert settings.chat_heartbeat_seconds == 15
    assert settings.chat_max_active_runs_per_user == 1
    assert settings.chat_runs_per_hour == 20
    assert settings.chat_runs_per_day == 100
    assert settings.chat_thread_retention_days == 365
    assert settings.chat_soft_delete_grace_days == 30
    assert settings.chat_file_context_mode == "deck_only"
    assert settings.chat_thinking_default_enabled is False
    assert settings.chat_web_search_enabled is False


def test_chat_web_search_cannot_be_enabled_without_a_new_contract() -> None:
    with pytest.raises(ValidationError):
        Settings(
            OFFICE_AI_DATABASE_URL="sqlite+aiosqlite:///:memory:",
            OFFICE_AI_REDIS_URL="redis://redis:6379/0",
            OFFICE_AI_CHAT_WEB_SEARCH_ENABLED=True,
        )
