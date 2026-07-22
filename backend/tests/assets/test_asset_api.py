import logging
from datetime import datetime
import json
from pathlib import Path
from uuid import UUID

from httpx import ASGITransport, AsyncClient
import pytest

from app.core.application import AuthServices, create_app
from app.services.asset_contracts import (
    AssetContent,
    AssetOperationError,
    AssetSummary,
    ProjectSummary,
)
from app.services.auth_registration import AuthOperationError
from app.services.auth_sessions import CurrentUser
from app.settings.config import Settings


PROJECT_ID = UUID("019f0000-0000-7000-8000-000000000201")
ASSET_ID = UUID("019f0000-0000-7000-8000-000000000202")
NOW = datetime(2026, 7, 22, 18, 0, 0)


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


class FakeUploadAuthSessions:
    def __init__(self) -> None:
        self.seen_tokens: list[str] = []

    async def authenticate_access(self, access_token: str) -> CurrentUser:
        self.seen_tokens.append(access_token)
        if access_token != "access-token":
            raise AuthOperationError("session_invalid", "Session 已失效", 401)
        return CurrentUser(
            user_id=UUID("019f0000-0000-7000-8000-000000000001"),
            phone_country_code="+86",
            phone_number="13800138000",
            role="user",
            status="active",
            credit_balance=0,
            must_change_password=False,
        )


class FakeAssetService:
    def __init__(self, asset_path: Path) -> None:
        self.asset_path = asset_path
        self.uploaded = b""
        self.upload_calls = 0
        self.project_changes = None
        self.deleted_project = None
        self.deleted_asset = None
        self.replay_asset = None
        self.upload_error = None

    @staticmethod
    def project() -> ProjectSummary:
        return ProjectSummary(PROJECT_ID, "经营分析", False, False, NOW, NOW)

    @staticmethod
    def asset() -> AssetSummary:
        return AssetSummary(
            ASSET_ID,
            PROJECT_ID,
            "经营报告.pdf",
            "document",
            "application/pdf",
            9,
            "a" * 64,
            "quarantined",
            NOW,
            NOW,
        )

    async def create_project(self, access_token: str, name: str):
        assert access_token == "access-token"
        assert name == "经营分析"
        return self.project()

    async def list_projects(self, access_token: str):
        assert access_token == "access-token"
        return [self.project()]

    async def update_project(self, access_token: str, project_id: UUID, changes: dict):
        assert access_token == "access-token"
        assert project_id == PROJECT_ID
        self.project_changes = changes
        return self.project()

    async def delete_project(self, access_token: str, project_id: UUID):
        assert access_token == "access-token"
        self.deleted_project = project_id

    async def upload_asset(self, **kwargs):
        self.upload_calls += 1
        if self.upload_error is not None:
            raise self.upload_error
        assert kwargs["access_token"] == "access-token"
        assert kwargs["project_id"] == PROJECT_ID
        assert kwargs["filename"] == "经营报告.pdf"
        assert kwargs["content_type"] == "application/pdf"
        assert kwargs["idempotency_key"] == "upload-api-1"
        self.uploaded = b"".join([chunk async for chunk in kwargs["content"]])
        return self.asset()

    async def find_upload_replay(
        self, access_token: str, idempotency_key: str
    ) -> AssetSummary | None:
        assert access_token == "access-token"
        assert idempotency_key
        return self.replay_asset

    async def list_assets(self, access_token: str, project_id: UUID | None = None):
        assert access_token == "access-token"
        assert project_id == PROJECT_ID
        return [self.asset()]

    async def get_asset(self, access_token: str, asset_id: UUID):
        assert access_token == "access-token"
        assert asset_id == ASSET_ID
        return self.asset()

    async def open_asset(self, access_token: str, asset_id: UUID):
        assert access_token == "access-token"
        assert asset_id == ASSET_ID
        return AssetContent(
            ASSET_ID, self.asset_path, "经营报告.pdf", "application/pdf"
        )

    async def delete_asset(self, access_token: str, asset_id: UUID):
        assert access_token == "access-token"
        self.deleted_asset = asset_id


def build_app(
    service,
    settings: Settings | None = None,
    upload_auth: FakeUploadAuthSessions | None = None,
):
    return create_app(
        settings=settings or Settings(),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(
            registration=object(),
            sessions=upload_auth or FakeUploadAuthSessions(),
        ),
        asset_services=service,
    )


async def raw_upload_request(app, headers: list[tuple[bytes, bytes]], body: bytes):
    return await raw_upload_messages(
        app,
        headers,
        [{"type": "http.request", "body": body, "more_body": False}],
    )


async def raw_upload_messages(app, headers, request_messages):
    receive_calls = 0
    request_messages = [*request_messages, {"type": "http.disconnect"}]
    response_messages = []

    async def receive():
        nonlocal receive_calls
        receive_calls += 1
        return request_messages.pop(0)

    async def send(message):
        response_messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/assets/uploads",
            "raw_path": b"/api/v1/assets/uploads",
            "query_string": b"",
            "root_path": "",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("test", 80),
            "state": {},
        },
        receive,
        send,
    )
    start = next(
        message
        for message in response_messages
        if message["type"] == "http.response.start"
    )
    payload = b"".join(
        message.get("body", b"")
        for message in response_messages
        if message["type"] == "http.response.body"
    )
    return start["status"], json.loads(payload), receive_calls


async def test_project_and_asset_api_exposes_scoped_crud_and_safe_content(
    tmp_path,
) -> None:
    asset_path = tmp_path / "asset.pdf"
    asset_path.write_bytes(b"%PDF-safe")
    service = FakeAssetService(asset_path)
    headers = {"Authorization": "Bearer access-token"}
    async with AsyncClient(
        transport=ASGITransport(app=build_app(service)), base_url="http://test"
    ) as client:
        created_project = await client.post(
            "/api/v1/projects", headers=headers, json={"name": "经营分析"}
        )
        projects = await client.get("/api/v1/projects", headers=headers)
        patched_project = await client.patch(
            f"/api/v1/projects/{PROJECT_ID}",
            headers=headers,
            json={"is_archived": True},
        )
        uploaded = await client.post(
            "/api/v1/assets/uploads",
            headers={**headers, "Idempotency-Key": "upload-api-1"},
            data={"project_id": str(PROJECT_ID)},
            files={"file": ("经营报告.pdf", b"%PDF-safe", "application/pdf")},
        )
        assets = await client.get(
            "/api/v1/assets", headers=headers, params={"project_id": str(PROJECT_ID)}
        )
        detail = await client.get(f"/api/v1/assets/{ASSET_ID}", headers=headers)
        preview = await client.get(
            f"/api/v1/assets/{ASSET_ID}/preview", headers=headers
        )
        download = await client.get(
            f"/api/v1/assets/{ASSET_ID}/download", headers=headers
        )
        deleted_asset = await client.delete(
            f"/api/v1/assets/{ASSET_ID}", headers=headers
        )
        deleted_project = await client.delete(
            f"/api/v1/projects/{PROJECT_ID}", headers=headers
        )

    assert created_project.status_code == 201
    assert projects.json()[0]["project_id"] == str(PROJECT_ID)
    assert patched_project.status_code == 200
    assert service.project_changes == {"is_archived": True}
    assert uploaded.status_code == 201
    assert uploaded.json()["processing_status"] == "quarantined"
    assert "storage_key" not in uploaded.json()
    assert service.uploaded == b"%PDF-safe"
    assert assets.json()[0]["asset_id"] == str(ASSET_ID)
    assert detail.status_code == 200
    assert preview.content == b"%PDF-safe"
    assert preview.headers["content-disposition"].startswith("inline")
    assert preview.headers["x-content-type-options"] == "nosniff"
    assert preview.headers["content-security-policy"] == "sandbox"
    assert download.headers["content-disposition"].startswith("attachment")
    assert download.headers["cache-control"] == "private, no-store"
    assert deleted_asset.status_code == 204
    assert deleted_project.status_code == 204
    assert service.deleted_asset == ASSET_ID
    assert service.deleted_project == PROJECT_ID


async def test_asset_api_uses_stable_error_envelope_without_echoing_path() -> None:
    class FailingService(FakeAssetService):
        async def get_asset(self, access_token: str, asset_id: UUID):
            raise AssetOperationError("asset_not_found", "资产不存在", 404)

    service = FailingService(Path("never-exposed"))
    async with AsyncClient(
        transport=ASGITransport(app=build_app(service)), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/api/v1/assets/{ASSET_ID}",
            headers={"Authorization": "Bearer access-token"},
        )

    assert response.status_code == 404
    assert response.json()["error"]["error_code"] == "asset_not_found"
    assert "never-exposed" not in response.text


async def test_asset_upload_requires_idempotency_key(tmp_path) -> None:
    asset_path = tmp_path / "asset.pdf"
    asset_path.write_bytes(b"%PDF-safe")
    async with AsyncClient(
        transport=ASGITransport(app=build_app(FakeAssetService(asset_path))),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/assets/uploads",
            headers={"Authorization": "Bearer access-token"},
            files={"file": ("report.pdf", b"%PDF-safe", "application/pdf")},
        )

    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "validation_error"


@pytest.mark.parametrize(
    "length_headers",
    (
        [(b"content-length", b"invalid")],
        [],
        [(b"transfer-encoding", b"chunked")],
    ),
)
async def test_asset_upload_rejects_unbounded_body_before_consuming_it(
    length_headers, tmp_path
) -> None:
    service = FakeAssetService(tmp_path / "asset.pdf")
    headers = [
        (b"authorization", b"Bearer access-token"),
        (b"idempotency-key", b"invalid-body"),
        (b"content-type", b"multipart/form-data; boundary=test"),
        *length_headers,
    ]

    status, payload, receive_calls = await raw_upload_request(
        build_app(service), headers, b"untrusted-body"
    )

    assert status == 413
    assert payload["error"]["error_code"] == "upload_body_invalid"
    assert payload["error"]["trace_id"]
    assert receive_calls == 0
    assert service.upload_calls == 0
    assert service.uploaded == b""


async def test_asset_upload_rejects_declared_oversize_before_consuming_it(
    tmp_path,
) -> None:
    service = FakeAssetService(tmp_path / "asset.pdf")
    settings = Settings(OFFICE_AI_MAX_FILE_BYTES=16)
    headers = [
        (b"authorization", b"Bearer access-token"),
        (b"idempotency-key", b"declared-oversize"),
        (b"content-type", b"multipart/form-data; boundary=test"),
        (b"content-length", str(settings.max_upload_body_bytes + 1).encode()),
    ]

    status, payload, receive_calls = await raw_upload_request(
        build_app(service, settings), headers, b"untrusted-body"
    )

    assert status == 413
    assert payload["error"]["error_code"] == "upload_body_too_large"
    assert receive_calls == 0
    assert service.upload_calls == 0


async def test_asset_upload_bounds_actual_bytes_when_length_is_underreported(
    tmp_path,
) -> None:
    service = FakeAssetService(tmp_path / "asset.pdf")
    settings = Settings(OFFICE_AI_MAX_FILE_BYTES=16)
    headers = [
        (b"authorization", b"Bearer access-token"),
        (b"idempotency-key", b"underreported-length"),
        (b"content-type", b"multipart/form-data; boundary=test"),
        (b"content-length", b"1"),
    ]

    status, payload, receive_calls = await raw_upload_request(
        build_app(service, settings),
        headers,
        b"x" * (settings.max_upload_body_bytes + 1),
    )

    assert status == 413
    assert payload["error"]["error_code"] == "upload_body_too_large"
    assert receive_calls == 1
    assert service.upload_calls == 0


@pytest.mark.parametrize(
    ("authorization", "expected_code"),
    (
        (None, "session_invalid"),
        (b"Bearer invalid-token", "session_invalid"),
    ),
)
async def test_asset_upload_authenticates_before_reading_multipart_body(
    authorization, expected_code, tmp_path
) -> None:
    service = FakeAssetService(tmp_path / "asset.pdf")
    upload_auth = FakeUploadAuthSessions()
    body = b"untrusted-multipart-body"
    headers = [
        (b"content-type", b"multipart/form-data; boundary=test"),
        (b"content-length", str(len(body)).encode()),
    ]
    if authorization is not None:
        headers.append((b"authorization", authorization))

    status, payload, receive_calls = await raw_upload_request(
        build_app(service, upload_auth=upload_auth), headers, body
    )

    assert status == 401
    assert payload["error"]["error_code"] == expected_code
    assert payload["error"]["trace_id"]
    assert receive_calls == 0
    assert service.upload_calls == 0
    assert upload_auth.seen_tokens == (
        [] if authorization is None else ["invalid-token"]
    )


async def test_asset_upload_replay_returns_before_reading_multipart_body(
    tmp_path,
) -> None:
    service = FakeAssetService(tmp_path / "asset.pdf")
    service.replay_asset = service.asset()
    body = b"untrusted-multipart-body"
    headers = [
        (b"authorization", b"Bearer access-token"),
        (b"idempotency-key", b"completed-upload"),
        (b"content-type", b"multipart/form-data; boundary=test"),
        (b"content-length", str(len(body)).encode()),
    ]

    status, payload, receive_calls = await raw_upload_request(
        build_app(service), headers, body
    )

    assert status == 201
    assert payload["asset_id"] == str(ASSET_ID)
    assert receive_calls == 0
    assert service.upload_calls == 0


async def test_asset_cleanup_failure_keeps_primary_http_error_and_logs_recovery(
    caplog, tmp_path
) -> None:
    service = FakeAssetService(tmp_path / "asset.pdf")
    error = AssetOperationError(
        "file_signature_invalid", "文件内容与声明类型不一致", 415
    )
    error.quarantine_cleanup_failed = True
    error.add_note("cleanup failed: PermissionError")
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
                    "Idempotency-Key": "cleanup-http",
                },
                files={"file": ("report.pdf", b"not-a-pdf", "application/pdf")},
            )

    assert response.status_code == 415
    assert response.json()["error"]["error_code"] == "file_signature_invalid"
    recovery = next(
        record for record in caplog.records if record.msg == "asset_recovery_failed"
    )
    assert recovery.error_code == "file_signature_invalid"
    assert recovery.cleanup_failed is True


@pytest.mark.parametrize("payload", ({"name": None}, {"is_archived": None}))
async def test_project_update_rejects_explicit_null(payload, tmp_path) -> None:
    service = FakeAssetService(tmp_path / "asset.pdf")
    async with AsyncClient(
        transport=ASGITransport(app=build_app(service)), base_url="http://test"
    ) as client:
        response = await client.patch(
            f"/api/v1/projects/{PROJECT_ID}",
            headers={"Authorization": "Bearer access-token"},
            json=payload,
        )

    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "validation_error"
    assert service.project_changes is None
