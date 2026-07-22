import asyncio

from app.core.database import DatabaseManager
from app.services.auth_bootstrap import bootstrap_admin
from app.services.auth_security import PasswordService
from app.settings.config import get_settings


async def run() -> None:
    settings = get_settings()
    database = DatabaseManager(settings.database_url)
    try:
        await bootstrap_admin(settings, database.session_factory, PasswordService())
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(run())
