from hashlib import sha256
from typing import Protocol


class CredentialBudgetStore(Protocol):
    async def reserve(
        self,
        *,
        credential_key: str,
        rpm_limit: int,
        tpm_limit: int,
        requested_tokens: int,
        requested_requests: int,
        window_seconds: int,
    ) -> bool: ...


class CredentialUsageLimiter:
    def __init__(self, store: CredentialBudgetStore) -> None:
        self._store = store

    async def acquire(
        self,
        *,
        credential_id,
        rpm_limit: int,
        tpm_limit: int,
        max_concurrency: int,
        active_count: int,
        requested_tokens: int,
        requested_requests: int = 1,
    ) -> bool:
        if active_count >= max_concurrency:
            return False
        credential_key = sha256(str(credential_id).encode("utf-8")).hexdigest()
        return await self._store.reserve(
            credential_key=credential_key,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            requested_tokens=requested_tokens,
            requested_requests=requested_requests,
            window_seconds=60,
        )


class RedisCredentialBudgetStore:
    def __init__(self, redis) -> None:
        self._redis = redis

    async def reserve(self, **values) -> bool:
        return await self._redis.reserve_credential_budget(**values)
