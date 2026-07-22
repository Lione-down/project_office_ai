import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.users import User
from app.services.auth_registration import AuthOperationError
from app.services.auth_security import PasswordService
from app.settings.config import Settings


_logger = logging.getLogger("office_ai.auth.bootstrap")
_PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


async def bootstrap_admin(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    passwords: PasswordService,
) -> bool:
    phone_number = settings.bootstrap_admin_phone
    password = settings.bootstrap_admin_password
    if phone_number is None or password is None:
        raise AuthOperationError(
            "bootstrap_configuration_missing",
            "管理员 Bootstrap runtime 配置缺失",
            503,
        )
    if not _PHONE_PATTERN.fullmatch(phone_number):
        raise AuthOperationError("bootstrap_phone_invalid", "管理员手机号无效")

    async with session_factory() as session, session.begin():
        existing_user = await session.scalar(
            select(User)
            .where(User.phone_country_code == "+86", User.phone_number == phone_number)
            .with_for_update()
        )
        if existing_user is not None:
            if existing_user.role != "admin":
                raise AuthOperationError(
                    "bootstrap_phone_conflict", "管理员手机号已被普通用户占用", 409
                )
            _logger.info("bootstrap_admin_already_exists")
            return False
        session.add(
            User(
                phone_country_code="+86",
                phone_number=phone_number,
                role="admin",
                status="active",
                password_hash=passwords.hash(password.get_secret_value()),
                must_change_password=False,
                credit_balance=0,
            )
        )
    _logger.info("bootstrap_admin_created")
    return True
