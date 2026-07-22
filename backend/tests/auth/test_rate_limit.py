import pytest

from app.services.rate_limit import RateLimitExceeded, RedisRateLimiter


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expirations: list[tuple[str, int]] = []

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self.expirations.append((key, seconds))
        return True


async def test_redis_rate_limiter_hashes_sensitive_keys_and_sets_expiry() -> None:
    redis = FakeRedis()
    limiter = RedisRateLimiter(redis)

    await limiter.check("login", "13800138000:127.0.0.1", 2, 60)
    await limiter.check("login", "13800138000:127.0.0.1", 2, 60)

    stored_key = next(iter(redis.values))
    assert "13800138000" not in stored_key
    assert "127.0.0.1" not in stored_key
    assert redis.expirations == [(stored_key, 60)]

    with pytest.raises(RateLimitExceeded) as error:
        await limiter.check("login", "13800138000:127.0.0.1", 2, 60)

    assert error.value.error_code == "rate_limit_exceeded"
    assert error.value.status_code == 429
