import asyncio
from collections.abc import Mapping
from typing import Protocol


class PingableDependency(Protocol):
    async def ping(self) -> None: ...


class DependencyReadinessChecker:
    def __init__(self, database: PingableDependency, redis: PingableDependency) -> None:
        self._dependencies = {"mysql": database, "redis": redis}

    async def check(self) -> Mapping[str, bool]:
        results = await asyncio.gather(
            *(dependency.ping() for dependency in self._dependencies.values()),
            return_exceptions=True,
        )
        return {
            name: not isinstance(result, BaseException)
            for name, result in zip(self._dependencies, results, strict=True)
        }
