import hashlib
from typing import Protocol


class RedisCounter(Protocol):
    async def incr(self, key: str) -> int: ...

    async def expire(self, key: str, seconds: int) -> bool: ...


class RateLimitExceeded(RuntimeError):
    error_code = "rate_limit_exceeded"
    message = "请求过于频繁，请稍后重试"
    status_code = 429


class RedisRateLimiter:
    def __init__(self, redis: RedisCounter) -> None:
        self._redis = redis

    async def check(
        self, scope: str, key: str, limit: int, window_seconds: int
    ) -> None:
        key_digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        redis_key = f"office_ai:rate:{scope}:{key_digest}"
        count = await self._redis.incr(redis_key)
        if count == 1:
            await self._redis.expire(redis_key, window_seconds)
        if count > limit:
            raise RateLimitExceeded()
