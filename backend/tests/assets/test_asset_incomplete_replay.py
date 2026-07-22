import asyncio
from dataclasses import dataclass
import json
from uuid import UUID

import pytest

from app.core.application import AuthServices, create_app
from app.models.file_assets import FileAsset
from app.models.users import User
from app.services.asset_contracts import AssetOperationError
from app.services.asset_management import AssetManagementService
from app.services.auth_sessions import CurrentUser
from app.storage.local import LocalStorageAdapter


USER_ID = UUID("019f0000-0000-7000-8000-000000000001")
PROJECT_ID = UUID("019f0000-0000-7000-8000-000000000201")
ASSET_ID = UUID("019f0000-0000-7000-8000-000000000202")


@dataclass
class FakeSessions:
    async def authenticate_access(self, access_token: str) -> CurrentUser:
        assert access_token in {"user-token", "access-token"}
        return CurrentUser(
            user_id=USER_ID,
            phone_country_code="+86",
            phone_number="13800138000",
            role="user",
            status="active",
            credit_balance=0,
            must_change_password=False,
        )


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


@pytest.fixture
def service(session_factory, tmp_path) -> AssetManagementService:
    return AssetManagementService(
        session_factory,
        FakeSessions(),
        LocalStorageAdapter(tmp_path),
        max_file_bytes=1024,
        max_image_bytes=512,
    )


@pytest.fixture(autouse=True)
async def user(session_factory) -> None:
    async with session_factory() as session, session.begin():
        session.add(
            User(
                id=USER_ID,
                phone_number="13800138000",
                password_hash="hash",
            )
        )


async def chunks(*values: bytes):
    for value in values:
        yield value


async def unread_chunks():
    raise AssertionError("幂等重放不应再次读取上传内容")
    yield b"unreachable"


async def upload_pdf(service: AssetManagementService, idempotency_key: str):
    return await service.upload_asset(
        access_token="user-token",
        project_id=None,
        filename="report.pdf",
        content_type="application/pdf",
        content=chunks(b"%PDF-1.7\n", b"safe"),
        idempotency_key=idempotency_key,
    )


@pytest.mark.parametrize("failure_mode", ("signature", "stream"))
async def test_concurrent_incomplete_replay_conflicts_then_failed_upload_can_retry(
    service, failure_mode
) -> None:
    project = await service.create_project("user-token", "经营分析")
    stream_started = asyncio.Event()
    release_stream = asyncio.Event()

    async def blocked_failure():
        stream_started.set()
        await release_stream.wait()
        if failure_mode == "signature":
            yield b"not-a-pdf"
            return
        yield b"partial-stream"
        raise RuntimeError("stream failed")

    first_upload = asyncio.create_task(
        service.upload_asset(
            access_token="user-token",
            project_id=project.project_id,
            filename="report.pdf",
            content_type="application/pdf",
            content=blocked_failure(),
            idempotency_key=f"concurrent-{failure_mode}",
        )
    )
    await stream_started.wait()

    second_error = None
    try:
        await service.upload_asset(
            access_token="user-token",
            project_id=project.project_id,
            filename="report.pdf",
            content_type="application/pdf",
            content=unread_chunks(),
            idempotency_key=f"concurrent-{failure_mode}",
        )
    except AssetOperationError as exception:
        second_error = exception
    finally:
        release_stream.set()

    expected_first_error = (
        AssetOperationError if failure_mode == "signature" else RuntimeError
    )
    with pytest.raises(expected_first_error):
        await first_upload

    retried = await upload_pdf(service, f"concurrent-{failure_mode}")

    assert second_error is not None
    assert second_error.error_code == "asset_upload_in_progress"
    assert second_error.status_code == 409
    assert retried.processing_status == "quarantined"


@pytest.mark.parametrize("processing_status", ("uploaded", "deleting"))
async def test_integrity_race_with_incomplete_checkpoint_returns_conflict(
    service, session_factory, monkeypatch, processing_status
) -> None:
    project = await service.create_project("user-token", "经营分析")
    existing_id = UUID(
        "019f0000-0000-7000-8000-000000000211"
        if processing_status == "uploaded"
        else "019f0000-0000-7000-8000-000000000212"
    )
    async with session_factory() as session, session.begin():
        session.add(
            FileAsset(
                id=existing_id,
                user_id=USER_ID,
                project_id=project.project_id,
                original_filename="report.pdf",
                file_category="document",
                mime_type="application/pdf",
                byte_size=0,
                sha256="0" * 64,
                storage_provider="local",
                storage_key=(f"users/{USER_ID}/quarantine/{existing_id}/original.pdf"),
                processing_status=processing_status,
                idempotency_key=f"integrity-race-{processing_status}",
            )
        )

    async def miss_initial_lookup(_user_id, _idempotency_key):
        return None

    monkeypatch.setattr(service._uploads, "find_replay", miss_initial_lookup)

    with pytest.raises(AssetOperationError) as captured:
        await service.upload_asset(
            access_token="user-token",
            project_id=project.project_id,
            filename="report.pdf",
            content_type="application/pdf",
            content=unread_chunks(),
            idempotency_key=f"integrity-race-{processing_status}",
        )

    assert captured.value.error_code == "asset_upload_in_progress"
    assert captured.value.status_code == 409


def build_app(service):
    return create_app(
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=FakeSessions()),
        asset_services=service,
    )


async def raw_upload_request(app, headers: list[tuple[bytes, bytes]], body: bytes):
    receive_calls = 0
    request_messages = [
        {"type": "http.request", "body": body, "more_body": False},
        {"type": "http.disconnect"},
    ]
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


@pytest.mark.parametrize("processing_status", ("uploaded", "deleting"))
async def test_incomplete_upload_replay_conflicts_before_reading_multipart_body(
    processing_status, service, session_factory, monkeypatch
) -> None:
    project = await service.create_project("user-token", "经营分析")
    async with session_factory() as session, session.begin():
        session.add(
            FileAsset(
                id=ASSET_ID,
                user_id=USER_ID,
                project_id=project.project_id,
                original_filename="经营报告.pdf",
                file_category="document",
                mime_type="application/pdf",
                byte_size=0,
                sha256="0" * 64,
                storage_provider="local",
                storage_key=service._storage.build_quarantine_key(
                    USER_ID, ASSET_ID, ".pdf"
                ),
                processing_status=processing_status,
                idempotency_key=f"incomplete-{processing_status}",
            )
        )

    upload_calls = 0

    async def unexpected_upload(**_kwargs):
        nonlocal upload_calls
        upload_calls += 1
        raise AssertionError("incomplete replay must not reach upload service")

    monkeypatch.setattr(service, "upload_asset", unexpected_upload)
    body = b"untrusted-multipart-body"
    headers = [
        (b"authorization", b"Bearer access-token"),
        (b"idempotency-key", f"incomplete-{processing_status}".encode()),
        (b"content-type", b"multipart/form-data; boundary=test"),
        (b"content-length", str(len(body)).encode()),
    ]

    status, payload, receive_calls = await raw_upload_request(
        build_app(service), headers, body
    )

    assert status == 409
    assert payload["error"]["error_code"] == "asset_upload_in_progress"
    assert payload["error"]["trace_id"]
    assert receive_calls == 0
    assert upload_calls == 0
