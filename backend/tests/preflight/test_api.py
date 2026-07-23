from datetime import datetime
from decimal import Decimal

from httpx import ASGITransport, AsyncClient

from app.core.application import AuthServices, create_app
from app.services.briefs.contracts import StructuredBrief
from app.services.briefs.dependencies import BriefServices
from app.services.preflight.contracts import (
    BriefSnapshot,
    ConflictFinding,
    PlannedOutputSnapshot,
    PreflightSnapshot,
)
from app.settings.config import Settings
from tests.briefs.helpers import BRIEF_GROUP_ID, valid_brief_payload
from tests.preflight.conftest import BRIEF_ID


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


class FakeSessions:
    async def authenticate_access(self, access_token: str):
        return object()


def brief_snapshot(*, revision: int = 1) -> BriefSnapshot:
    return BriefSnapshot(
        brief_id=BRIEF_ID,
        brief_group_id=BRIEF_GROUP_ID,
        revision=revision,
        status="draft",
        content=StructuredBrief.model_validate(valid_brief_payload()),
        content_checksum="a" * 64,
        source_snapshot={},
        estimated_credits=None,
        confirmed_at=None,
    )


def preflight_snapshot(*, status: str = "preflight") -> PreflightSnapshot:
    return PreflightSnapshot(
        brief_id=BRIEF_ID,
        brief_group_id=BRIEF_GROUP_ID,
        revision=1,
        status=status,
        conflicts=(
            ConflictFinding(
                code="narrative_low_confidence",
                level="needs_confirmation",
                message="请确认低置信度叙述",
            ),
        ),
        outputs=(
            PlannedOutputSnapshot(
                skill_code="ppt.sales-business-review.v1",
                kind="pptx",
                title="销售经营汇报",
                template_code="ppt.executive-blue.v1",
                template_version="1.0.0",
                estimated_credits=800,
            ),
        ),
        credit_multiplier=Decimal("1.0000"),
        estimated_credits=800,
        has_blockers=False,
        confirmed_at=datetime(2026, 7, 23, 12, 0) if status == "queued" else None,
    )


class FakeWorkflow:
    def __init__(self) -> None:
        self.calls = []

    async def get(self, access_token, brief_id):
        self.calls.append(("get", access_token, brief_id))
        return brief_snapshot()

    async def revise(self, access_token, brief_id, command):
        self.calls.append(("revise", access_token, brief_id, command))
        return brief_snapshot(revision=2)

    async def preflight(self, access_token, command):
        self.calls.append(("preflight", access_token, command))
        return preflight_snapshot()

    async def confirm(self, access_token, brief_id, *, accepted_estimated_credits):
        self.calls.append(
            ("confirm", access_token, brief_id, accepted_estimated_credits)
        )
        return preflight_snapshot(status="queued")


def build_app(workflow: FakeWorkflow):
    return create_app(
        settings=Settings(),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=FakeSessions()),
        brief_services=BriefServices(
            skills=object(),
            generation=object(),
            workflow=workflow,
        ),
    )


async def test_brief_detail_and_revision_endpoints_map_owner_commands() -> None:
    workflow = FakeWorkflow()
    headers = {"Authorization": "Bearer access-token"}
    async with AsyncClient(
        transport=ASGITransport(app=build_app(workflow)),
        base_url="http://test",
    ) as client:
        detail = await client.get(f"/api/v1/briefs/{BRIEF_ID}", headers=headers)
        revised = await client.patch(
            f"/api/v1/briefs/{BRIEF_ID}",
            headers=headers,
            json={
                "expected_revision": 1,
                "goal": "形成董事会季度销售复盘",
                "template_versions": [
                    {
                        "template_code": "ppt.executive-blue.v1",
                        "version": "1.0.0",
                    }
                ],
            },
        )

    assert detail.status_code == 200
    assert detail.headers["cache-control"] == "private, no-store"
    assert revised.status_code == 201
    assert revised.json()["revision"] == 2
    assert workflow.calls[0] == ("get", "access-token", BRIEF_ID)
    assert workflow.calls[1][0:3] == ("revise", "access-token", BRIEF_ID)
    assert workflow.calls[1][3].goal == "形成董事会季度销售复盘"


async def test_preflight_and_confirm_endpoints_keep_credit_acceptance_separate() -> (
    None
):
    workflow = FakeWorkflow()
    headers = {"Authorization": "Bearer access-token"}
    async with AsyncClient(
        transport=ASGITransport(app=build_app(workflow)),
        base_url="http://test",
    ) as client:
        checked = await client.post(
            "/api/v1/generations/preflight",
            headers=headers,
            json={"brief_id": str(BRIEF_ID)},
        )
        confirmed = await client.post(
            f"/api/v1/briefs/{BRIEF_ID}/confirm",
            headers=headers,
            json={"accepted_estimated_credits": 800},
        )

    assert checked.status_code == 200
    assert checked.json()["credit_multiplier"] == "1.0000"
    assert checked.json()["estimated_credits"] == 800
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "queued"
    assert confirmed.headers["cache-control"] == "private, no-store"
    assert workflow.calls[0][0] == "preflight"
    assert workflow.calls[0][2].one_click is False
    assert workflow.calls[1] == ("confirm", "access-token", BRIEF_ID, 800)


async def test_preflight_rejects_unknown_fields_before_workflow() -> None:
    workflow = FakeWorkflow()
    async with AsyncClient(
        transport=ASGITransport(app=build_app(workflow)),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/generations/preflight",
            headers={"Authorization": "Bearer access-token"},
            json={"brief_id": str(BRIEF_ID), "unexpected": True},
        )

    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "validation_error"
    assert workflow.calls == []
