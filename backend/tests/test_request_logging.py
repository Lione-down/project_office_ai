import logging

from httpx import ASGITransport, AsyncClient

from app.main import create_app


class AlwaysReady:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


async def test_request_log_record_contains_trace_id(caplog) -> None:
    app = create_app(readiness_checker=AlwaysReady())

    with caplog.at_level(logging.INFO, logger="office_ai.request"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/health/live", headers={"X-Trace-ID": "trace-log"}
            )

    matching_records = [
        record
        for record in caplog.records
        if record.getMessage() == "request_completed"
    ]
    assert response.status_code == 200
    assert matching_records
    assert matching_records[-1].trace_id == "trace-log"
    assert "do-not-log-this" not in caplog.text
