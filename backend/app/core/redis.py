from pydantic import SecretStr
from redis.asyncio import Redis


class RedisManager:
    def __init__(self, redis_url: SecretStr) -> None:
        self._client = Redis.from_url(
            redis_url.get_secret_value(), decode_responses=True
        )

    async def ping(self) -> None:
        await self._client.ping()

    async def close(self) -> None:
        await self._client.aclose()
