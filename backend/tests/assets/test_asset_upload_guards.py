import asyncio
import logging
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.asset_contracts import AssetOperationError
from app.settings.config import Settings
from tests.assets.test_asset_api import (
    FakeAssetService,
    build_app,
    raw_upload_messages,
)


async def test_asset_upload_rejects_before_parser_spools_underreported_body(
    monkeypatch, tmp_path
) -> None:
    service = FakeAssetService(tmp_path / "asset.pdf")
    settings = Settings(OFFICE_AI_MAX_FILE_BYTES=2 * 1024 * 1024)
    parser_spools = []

    def track_parser_spool(*args, **kwargs):
        spool = tempfile.SpooledTemporaryFile(*args, **kwargs)
        parser_spools.append(spool)
        return spool

    monkeypatch.setattr(
        "starlette.formparsers.SpooledTemporaryFile", track_parser_spool
    )
    prefix = (
        b"--test\r\n"
        b'Content-Disposition: form-data; name="file"; filename="report.pdf"\r\n'
        b"Content-Type: application/pdf\r\n\r\n"
    )
    first = prefix + b"x" * (1024 * 1024 + 1)
    second = b"x" * settings.max_upload_body_bytes
    headers = [
        (b"authorization", b"Bearer access-token"),
        (b"idempotency-key", b"parser-spool-gate"),
        (b"content-type", b"multipart/form-data; boundary=test"),
        (b"content-length", b"1"),
    ]

    status, payload, receive_calls = await raw_upload_messages(
        build_app(service, settings),
        headers,
        [
            {"type": "http.request", "body": first, "more_body": True},
            {"type": "http.request", "body": second, "more_body": False},
        ],
    )

    assert status == 413
    assert payload["error"]["error_code"] == "upload_body_too_large"
    assert receive_calls == 2
    assert parser_spools == []
    assert service.upload_calls == 0


async def test_asset_direct_cleanup_error_logs_recovery(caplog, tmp_path) -> None:
    service = FakeAssetService(tmp_path / "asset.pdf")
    service.upload_error = AssetOperationError(
        "quarantine_cleanup_failed", "上传暂存文件清理失败", 500
    )

    with caplog.at_level(logging.ERROR, logger="office_ai.error"):
        async with AsyncClient(
            transport=ASGITransport(app=build_app(service)),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/assets/uploads",
                headers={
                    "Authorization": "Bearer access-token",
                    "Idempotency-Key": "direct-cleanup-error",
                },
                files={"file": ("report.pdf", b"not-a-pdf", "application/pdf")},
            )

    assert response.status_code == 500
    assert response.json()["error"]["error_code"] == "quarantine_cleanup_failed"
    assert any(record.msg == "asset_recovery_failed" for record in caplog.records)


async def test_asset_unexpected_stream_cleanup_logs_recovery(caplog, tmp_path) -> None:
    service = FakeAssetService(tmp_path / "asset.pdf")
    error = OSError("stream failed")
    error.quarantine_cleanup_failed = True
    service.upload_error = error

    with caplog.at_level(logging.ERROR, logger="office_ai.error"):
        async with AsyncClient(
            transport=ASGITransport(app=build_app(service), raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/assets/uploads",
                headers={
                    "Authorization": "Bearer access-token",
                    "Idempotency-Key": "unexpected-cleanup-error",
                },
                files={"file": ("report.pdf", b"not-a-pdf", "application/pdf")},
            )

    assert response.status_code == 500
    assert response.json()["error"]["error_code"] == "internal_error"
    assert any(record.msg == "asset_recovery_failed" for record in caplog.records)


async def test_asset_cancelled_cleanup_logs_recovery(caplog, tmp_path) -> None:
    service = FakeAssetService(tmp_path / "asset.pdf")
    error = asyncio.CancelledError()
    error.quarantine_cleanup_failed = True
    service.upload_error = error

    with caplog.at_level(logging.ERROR, logger="office_ai.error"):
        async with AsyncClient(
            transport=ASGITransport(app=build_app(service)),
            base_url="http://test",
        ) as client:
            with pytest.raises(RuntimeError, match="No response returned"):
                await client.post(
                    "/api/v1/assets/uploads",
                    headers={
                        "Authorization": "Bearer access-token",
                        "Idempotency-Key": "cancelled-cleanup-error",
                    },
                    files={"file": ("report.pdf", b"not-a-pdf", "application/pdf")},
                )

    assert any(record.msg == "asset_recovery_failed" for record in caplog.records)


async def test_asset_upload_rejects_extra_multipart_file(tmp_path) -> None:
    service = FakeAssetService(tmp_path / "asset.pdf")
    async with AsyncClient(
        transport=ASGITransport(app=build_app(service)), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/assets/uploads",
            headers={
                "Authorization": "Bearer access-token",
                "Idempotency-Key": "extra-file",
            },
            files=[
                ("file", ("report.pdf", b"%PDF-safe", "application/pdf")),
                ("extra", ("other.txt", b"other", "text/plain")),
            ],
        )

    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "upload_form_invalid"
    assert service.upload_calls == 0
