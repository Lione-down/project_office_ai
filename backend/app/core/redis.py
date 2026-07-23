import json

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

    async def reserve_credential_budget(
        self,
        *,
        credential_key: str,
        rpm_limit: int,
        tpm_limit: int,
        requested_tokens: int,
        requested_requests: int,
        window_seconds: int,
    ) -> bool:
        script = """
        local requests = redis.call('INCRBY', KEYS[1], ARGV[5])
        if requests == tonumber(ARGV[5]) then redis.call('EXPIRE', KEYS[1], ARGV[4]) end
        local tokens = redis.call('INCRBY', KEYS[2], ARGV[1])
        if tokens == tonumber(ARGV[1]) then redis.call('EXPIRE', KEYS[2], ARGV[4]) end
        if requests > tonumber(ARGV[2]) or tokens > tonumber(ARGV[3]) then
          redis.call('DECRBY', KEYS[1], ARGV[5])
          redis.call('DECRBY', KEYS[2], ARGV[1])
          return 0
        end
        return 1
        """
        result = await self._client.eval(
            script,
            2,
            f"office_ai:credential:{credential_key}:rpm",
            f"office_ai:credential:{credential_key}:tpm",
            requested_tokens,
            rpm_limit,
            tpm_limit,
            window_seconds,
            requested_requests,
        )
        return bool(result)

    async def enqueue_generation(self, queue_key: str, payload: dict) -> None:
        await self._client.rpush(
            queue_key,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )

    async def dequeue_generation(
        self, queue_key: str, timeout_seconds: int = 2
    ) -> dict | None:
        item = await self._client.blpop(queue_key, timeout=timeout_seconds)
        if item is None:
            return None
        return json.loads(item[1])

    async def close(self) -> None:
        await self._client.aclose()
