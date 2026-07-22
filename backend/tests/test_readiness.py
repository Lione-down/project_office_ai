from app.controllers.health import DependencyReadinessChecker


class AvailableDependency:
    async def ping(self) -> None:
        return None


class UnavailableDependency:
    async def ping(self) -> None:
        raise ConnectionError("dependency unavailable")


async def test_dependency_readiness_checker_reports_each_dependency() -> None:
    checker = DependencyReadinessChecker(
        database=AvailableDependency(), redis=UnavailableDependency()
    )

    result = await checker.check()

    assert result == {"mysql": True, "redis": False}
