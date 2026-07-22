from pydantic import SecretStr
from redis.asyncio import Redis


class RedisManager:
    def __init__(self, redis_url: SecretStr) -> None:
        self._client = Redis.from_url(
            redis_url.get_secret_value(), decode_responses=True
        )

    async def ping(self) -> None:
        await self._client.ping()

    async def incr(self, key: str) -> int:
        return await self._client.incr(key)

    async def expire(self, key: str, seconds: int) -> bool:
        return await self._client.expire(key, seconds)

    async def close(self) -> None:
        await self._client.aclose()
