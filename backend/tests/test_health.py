from collections.abc import Mapping

from httpx import ASGITransport, AsyncClient

from app.main import create_app


class StubReadinessChecker:
    def __init__(self, result: Mapping[str, bool]) -> None:
        self._result = result

    async def check(self) -> Mapping[str, bool]:
        return self._result


async def test_liveness_returns_live_with_trace_id() -> None:
    app = create_app(readiness_checker=StubReadinessChecker({}))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/health/live", headers={"X-Trace-ID": "trace-live"}
        )

    assert response.status_code == 200
    assert response.json() == {"status": "live", "trace_id": "trace-live"}
    assert response.headers["X-Trace-ID"] == "trace-live"


async def test_readiness_returns_ready_when_critical_dependencies_are_available() -> (
    None
):
    app = create_app(
        readiness_checker=StubReadinessChecker({"mysql": True, "redis": True})
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["dependencies"] == {"mysql": "up", "redis": "up"}
    assert response.json()["trace_id"] == response.headers["X-Trace-ID"]


async def test_readiness_returns_sanitized_error_when_dependency_is_unavailable() -> (
    None
):
    app = create_app(
        readiness_checker=StubReadinessChecker({"mysql": False, "redis": True})
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")

    payload = response.json()
    assert response.status_code == 503
    assert payload["error"] == {
        "error_code": "service_not_ready",
        "message": "服务依赖尚未就绪",
        "trace_id": response.headers["X-Trace-ID"],
    }
    assert payload["readiness"] == {
        "status": "not_ready",
        "dependencies": {"mysql": "down", "redis": "up"},
    }
    assert "password" not in response.text.lower()
    assert "redis://" not in response.text.lower()


async def test_unknown_route_uses_stable_error_envelope() -> None:
    app = create_app(readiness_checker=StubReadinessChecker({}))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "error_code": "not_found",
            "message": "请求的资源不存在",
            "trace_id": response.headers["X-Trace-ID"],
        }
    }
