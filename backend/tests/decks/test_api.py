from uuid import UUID

from httpx import ASGITransport, AsyncClient

from app.core.application import AuthServices, create_app
from app.services.decks.contracts import DeckBrief, DeckDraftSnapshot
from app.services.generation_contracts import GenerationSnapshot
from app.settings.config import Settings


MESSAGE_ID = UUID("019fad20-0000-7000-8000-000000000001")
DRAFT_ID = UUID("019fad20-0000-7000-8000-000000000002")
THREAD_ID = UUID("019fad20-0000-7000-8000-000000000003")
REVISION_ID = UUID("019fad20-0000-7000-8000-000000000004")
PROJECT_ID = UUID("019fad20-0000-7000-8000-000000000005")
MODEL_ID = UUID("019fad20-0000-7000-8000-000000000006")
TASK_ID = UUID("019fad20-0000-7000-8000-000000000007")


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


def deck() -> DeckBrief:
    return DeckBrief.model_validate(
        {
            "schema_version": "deck-brief.v1",
            "topic": "季度复盘",
            "audience": "管理层",
            "language": "zh-CN",
            "style": "清晰、专业",
            "source_mode": "inspiration",
            "skill_code": "ppt.sales-business-review.v1",
            "slides": [
                {
                    "slide_id": f"019fad20-0000-7000-8000-{index:012d}",
                    "title": title,
                    "purpose": "说明本页目标",
                    "body": ["要点一", "要点二"],
                    "speaker_notes": "",
                    "visual_suggestion": "",
                    "provenance": [{"kind": "agnes_inference", "evidence_ids": []}],
                }
                for index, title in enumerate(("开场", "分析", "结论"), start=10)
            ],
        }
    )


def snapshot(
    *,
    revision: int = 1,
    status: str = "draft",
    preflight_snapshot: dict | None = None,
) -> DeckDraftSnapshot:
    return DeckDraftSnapshot(
        draft_id=DRAFT_ID,
        thread_id=THREAD_ID,
        source_message_id=MESSAGE_ID,
        revision_id=REVISION_ID,
        revision=revision,
        status=status,
        content=deck(),
        content_checksum="a" * 64,
        preflight_snapshot=preflight_snapshot,
        generation_task_id=None,
        confirmed_at=None,
    )


class DeckStub:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def create(
        self, access_token, message_id, command, idempotency_key, *, trace_id
    ):
        self.calls.append(
            ("create", access_token, message_id, command, idempotency_key, trace_id)
        )
        return snapshot()

    async def get(self, access_token, draft_id):
        self.calls.append(("get", access_token, draft_id))
        return snapshot()

    async def update(self, access_token, draft_id, command):
        self.calls.append(("update", access_token, draft_id, command))
        return snapshot(revision=2)

    async def confirm(self, access_token, draft_id, command):
        self.calls.append(("confirm", access_token, draft_id, command))
        return snapshot(status="confirmed")

    async def preflight(self, access_token, draft_id):
        self.calls.append(("preflight", access_token, draft_id))
        return snapshot(
            status="ready",
            preflight_snapshot={
                "estimated_credits": 800,
                "has_blockers": False,
                "conflicts": [],
            },
        )

    async def generate(self, access_token, draft_id, command, idempotency_key):
        self.calls.append(
            ("generate", access_token, draft_id, command, idempotency_key)
        )
        return GenerationSnapshot(
            task_id=TASK_ID,
            brief_id=DRAFT_ID,
            status="queued",
            progress=0,
            estimated_credits=800,
            settled_credits=0,
            error_category=None,
            cancel_requested=False,
            steps=(),
        )


async def test_deck_api_exposes_versioned_no_store_workflow_contract() -> None:
    service = DeckStub()
    app = create_app(
        settings=Settings(),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=object()),
        deck_services=service,
    )
    headers = {"Authorization": "Bearer access-token"}
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        created = await client.post(
            f"/api/v1/chat/messages/{MESSAGE_ID}/deck-drafts",
            headers={**headers, "Idempotency-Key": "deck-create-api-001"},
            json={
                "project_id": str(PROJECT_ID),
                "model_id": str(MODEL_ID),
                "topic": "季度复盘",
                "audience": "管理层",
                "slide_count": 3,
                "language": "zh-CN",
                "style": "清晰、专业",
                "source_mode": "inspiration",
                "skill_code": "ppt.sales-business-review.v1",
                "asset_ids": [],
            },
        )
        detail = await client.get(
            f"/api/v1/deck-drafts/{DRAFT_ID}",
            headers=headers,
        )
        updated = await client.patch(
            f"/api/v1/deck-drafts/{DRAFT_ID}",
            headers=headers,
            json={"expected_revision": 1, "content": deck().model_dump(mode="json")},
        )
        confirmed = await client.post(
            f"/api/v1/deck-drafts/{DRAFT_ID}/confirm",
            headers=headers,
            json={"expected_revision": 1, "high_risk_confirmed": False},
        )
        preflight = await client.post(
            f"/api/v1/deck-drafts/{DRAFT_ID}/preflight",
            headers=headers,
        )
        generated = await client.post(
            f"/api/v1/deck-drafts/{DRAFT_ID}/generations",
            headers={**headers, "Idempotency-Key": "deck-generation-api-001"},
            json={"expected_revision": 1, "accepted_estimated_credits": 800},
        )

    assert [
        response.status_code
        for response in (
            created,
            detail,
            updated,
            confirmed,
            preflight,
            generated,
        )
    ] == [201, 200, 201, 200, 200, 201]
    assert all(
        response.headers["cache-control"] == "private, no-store"
        for response in (
            created,
            detail,
            updated,
            confirmed,
            preflight,
            generated,
        )
    )
    assert updated.json()["revision"] == 2
    assert generated.json()["task_id"] == str(TASK_ID)
    assert service.calls[0][0:5] == (
        "create",
        "access-token",
        MESSAGE_ID,
        service.calls[0][3],
        "deck-create-api-001",
    )
    assert service.calls[2][3].expected_revision == 1
    assert service.calls[5][4] == "deck-generation-api-001"
