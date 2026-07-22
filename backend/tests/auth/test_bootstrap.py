import logging

import pytest
from sqlalchemy import func, select

from app.models.users import User
from app.services.auth_bootstrap import bootstrap_admin
from app.services.auth_registration import AuthOperationError
from app.services.auth_security import PasswordService
from app.settings.config import Settings


async def test_admin_bootstrap_reads_runtime_settings_and_is_idempotent(
    session_factory, caplog
) -> None:
    settings = Settings(
        OFFICE_AI_BOOTSTRAP_ADMIN_PHONE="13900139000",
        OFFICE_AI_BOOTSTRAP_ADMIN_PASSWORD="admin-correct-horse-battery-staple",
    )
    passwords = PasswordService()

    with caplog.at_level(logging.INFO):
        first_result = await bootstrap_admin(settings, session_factory, passwords)
        second_result = await bootstrap_admin(settings, session_factory, passwords)

    async with session_factory() as session:
        admin = await session.scalar(select(User))
        user_count = await session.scalar(select(func.count()).select_from(User))

    assert first_result is True
    assert second_result is False
    assert user_count == 1
    assert admin.role == "admin"
    assert passwords.verify(admin.password_hash, "admin-correct-horse-battery-staple")
    assert "admin-correct-horse-battery-staple" not in caplog.text
    assert "13900139000" not in caplog.text


async def test_admin_bootstrap_fails_closed_without_runtime_credentials(
    session_factory,
) -> None:
    with pytest.raises(AuthOperationError) as error:
        await bootstrap_admin(Settings(), session_factory, PasswordService())

    assert error.value.error_code == "bootstrap_configuration_missing"
