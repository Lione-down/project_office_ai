from datetime import datetime
from uuid import UUID

from httpx import ASGITransport, AsyncClient

from app.core.application import AuthServices, create_app
from app.services.terminology.contracts import (
    TermItemSummary,
    TermLibrarySnapshot,
)
from app.services.terminology.service import TerminologyOperationError
from app.settings.config import Settings


LIBRARY_ID = UUID("019f3000-0000-7000-8000-000000000001")
ITEM_ID = UUID("019f3000-0000-7000-8000-000000000002")
PROJECT_ID = UUID("019f3000-0000-7000-8000-000000000003")
NOW = datetime(2026, 7, 23, 21, 0, 0)


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


class FakeSessions:
    async def authenticate_access(self, access_token: str):
        return object()


def snapshot(version: int = 1, *, items=()) -> TermLibrarySnapshot:
    return TermLibrarySnapshot(
        library_id=LIBRARY_ID,
        project_id=PROJECT_ID,
        name="销售口径",
        description="项目标准",
        status="active",
        version=version,
        created_at=NOW,
        items=items,
    )


class FakeTerminologyService:
    def __init__(self) -> None:
        self.calls = []
        self.current_items = ()

    async def create_library(self, access_token: str, **values):
        self.calls.append(("create_library", access_token, values))
        return snapshot()

    async def list_libraries(self, access_token: str):
        self.calls.append(("list_libraries", access_token))
        return [snapshot()]

    async def get_library(self, access_token: str, library_id: UUID, **values):
        self.calls.append(("get_library", access_token, library_id, values))
        return snapshot(values.get("version") or 1, items=self.current_items)

    async def update_library(self, access_token: str, library_id: UUID, changes: dict):
        self.calls.append(("update_library", access_token, library_id, changes))
        return snapshot(2)

    async def delete_library(self, access_token: str, library_id: UUID):
        self.calls.append(("delete_library", access_token, library_id))

    async def create_item(self, access_token: str, library_id: UUID, **values):
        self.calls.append(("create_item", access_token, library_id, values))
        self.current_items = (
            TermItemSummary(
                item_id=ITEM_ID,
                canonical_term=values["canonical_term"],
                aliases=tuple(values["aliases"]),
                unit=values["unit"],
                definition=values["definition"],
                metric_scope=values["metric_scope"],
                priority=values["priority"],
            ),
        )
        return snapshot(
            2,
            items=self.current_items,
        )

    async def update_item(
        self,
        access_token: str,
        library_id: UUID,
        item_id: UUID,
        changes: dict,
    ):
        self.calls.append(("update_item", access_token, library_id, item_id, changes))
        return snapshot(3)

    async def delete_item(self, access_token: str, library_id: UUID, item_id: UUID):
        self.calls.append(("delete_item", access_token, library_id, item_id))
        return snapshot(4)


def build_app(service):
    return create_app(
        settings=Settings(),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=FakeSessions()),
        terminology_services=service,
    )


async def test_term_library_api_exposes_versioned_crud() -> None:
    service = FakeTerminologyService()
    headers = {"Authorization": "Bearer access-token"}
    async with AsyncClient(
        transport=ASGITransport(app=build_app(service)), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/term-libraries",
            headers=headers,
            json={
                "name": "销售口径",
                "description": "项目标准",
                "project_id": str(PROJECT_ID),
            },
        )
        listed = await client.get("/api/v1/term-libraries", headers=headers)
        historical = await client.get(
            f"/api/v1/term-libraries/{LIBRARY_ID}?version=1", headers=headers
        )
        updated = await client.patch(
            f"/api/v1/term-libraries/{LIBRARY_ID}",
            headers=headers,
            json={"name": "新销售口径"},
        )
        deleted = await client.delete(
            f"/api/v1/term-libraries/{LIBRARY_ID}", headers=headers
        )

    assert created.status_code == 201
    assert created.json()["library_id"] == str(LIBRARY_ID)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert historical.json()["version"] == 1
    assert updated.json()["version"] == 2
    assert deleted.status_code == 204
    assert (
        "get_library",
        "access-token",
        LIBRARY_ID,
        {"version": 1},
    ) in service.calls


async def test_term_item_api_mutates_new_library_snapshots() -> None:
    service = FakeTerminologyService()
    headers = {"Authorization": "Bearer access-token"}
    async with AsyncClient(
        transport=ASGITransport(app=build_app(service)), base_url="http://test"
    ) as client:
        created = await client.post(
            f"/api/v1/term-libraries/{LIBRARY_ID}/items",
            headers=headers,
            json={
                "canonical_term": "销售额",
                "aliases": ["营收"],
                "unit": "CNY",
                "definition": "确认收入",
                "metric_scope": "含税销售额",
                "priority": 10,
            },
        )
        listed = await client.get(
            f"/api/v1/term-libraries/{LIBRARY_ID}/items?version=2",
            headers=headers,
        )
        updated = await client.patch(
            f"/api/v1/term-libraries/{LIBRARY_ID}/items/{ITEM_ID}",
            headers=headers,
            json={"aliases": ["营业收入"]},
        )
        deleted = await client.delete(
            f"/api/v1/term-libraries/{LIBRARY_ID}/items/{ITEM_ID}",
            headers=headers,
        )

    assert created.status_code == 201
    assert created.json()["version"] == 2
    assert listed.status_code == 200
    assert listed.json()[0]["item_id"] == str(ITEM_ID)
    assert updated.json()["version"] == 3
    assert deleted.status_code == 204


async def test_terminology_api_uses_stable_error_envelope() -> None:
    class MissingService(FakeTerminologyService):
        async def get_library(self, access_token, library_id, **values):
            raise TerminologyOperationError(
                "term_library_not_found", "术语库不存在", 404
            )

    async with AsyncClient(
        transport=ASGITransport(app=build_app(MissingService())),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/api/v1/term-libraries/{LIBRARY_ID}",
            headers={"Authorization": "Bearer access-token"},
        )

    assert response.status_code == 404
    assert response.json()["error"]["error_code"] == "term_library_not_found"
    assert response.json()["error"]["message"] == "术语库不存在"


async def test_terminology_api_rejects_unknown_fields() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=build_app(FakeTerminologyService())),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/term-libraries",
            headers={"Authorization": "Bearer access-token"},
            json={"name": "销售口径", "unexpected": "value"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "validation_error"
