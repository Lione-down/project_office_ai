from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)


class DatabaseManager:
    def __init__(self, database_url: SecretStr) -> None:
        self._engine: AsyncEngine = create_async_engine(
            database_url.get_secret_value(),
            pool_pre_ping=True,
            hide_parameters=True,
        )
        self.session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def ping(self) -> None:
        async with self._engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()
