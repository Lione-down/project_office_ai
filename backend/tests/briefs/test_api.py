from httpx import ASGITransport, AsyncClient

from app.core.application import AuthServices, create_app
from app.services.briefs.contracts import (
    BriefRevisionSnapshot,
    StructuredBrief,
)
from app.services.briefs.dependencies import BriefServices
from app.services.briefs.service import BriefOperationError
from app.settings.config import Settings
from app.skills.catalog import ALPHA_SKILLS
from tests.briefs.helpers import (
    ASSET_ID,
    BRIEF_GROUP_ID,
    MODEL_ID,
    PROJECT_ID,
    valid_brief_payload,
)


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


class FakeSessions:
    async def authenticate_access(self, access_token: str):
        return object()


class FakeSkills:
    def __init__(self) -> None:
        self.calls = []

    async def list_published(self, access_token: str):
        self.calls.append(("list", access_token))
        return ALPHA_SKILLS

    async def get_published(self, access_token: str, skill_code: str):
        self.calls.append(("get", access_token, skill_code))
        return ALPHA_SKILLS[0]


class FakeBriefGeneration:
    def __init__(self) -> None:
        self.calls = []

    async def generate(self, access_token: str, command, *, trace_id: str):
        self.calls.append((access_token, command, trace_id))
        return BriefRevisionSnapshot(
            brief_id=BRIEF_GROUP_ID,
            brief_group_id=BRIEF_GROUP_ID,
            revision=1,
            status="draft",
            content=StructuredBrief.model_validate(valid_brief_payload()),
            content_checksum="a" * 64,
        )


def build_app(skills=None, generation=None):
    return create_app(
        settings=Settings(),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=FakeSessions()),
        brief_services=BriefServices(
            skills=skills or FakeSkills(),
            generation=generation or FakeBriefGeneration(),
        ),
    )


async def test_skill_api_lists_and_gets_published_contracts() -> None:
    skills = FakeSkills()
    headers = {"Authorization": "Bearer access-token"}
    async with AsyncClient(
        transport=ASGITransport(app=build_app(skills=skills)),
        base_url="http://test",
    ) as client:
        listed = await client.get("/api/v1/skills", headers=headers)
        detail = await client.get(
            "/api/v1/skills/ppt.sales-business-review.v1",
            headers=headers,
        )

    assert listed.status_code == 200
    assert [item["skill_code"] for item in listed.json()] == [
        skill.skill_code for skill in ALPHA_SKILLS
    ]
    assert detail.status_code == 200
    assert detail.json()["version"] == "1.0.0"
    assert skills.calls == [
        ("list", "access-token"),
        ("get", "access-token", "ppt.sales-business-review.v1"),
    ]


async def test_brief_generate_api_uses_versioned_ids_and_trace() -> None:
    generation = FakeBriefGeneration()
    async with AsyncClient(
        transport=ASGITransport(app=build_app(generation=generation)),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/briefs/generate",
            headers={
                "Authorization": "Bearer access-token",
                "X-Trace-ID": "trace-api-brief",
            },
            json={
                "project_id": str(PROJECT_ID),
                "asset_ids": [str(ASSET_ID)],
                "term_library_versions": [],
                "skill_codes": ["ppt.sales-business-review.v1"],
                "model_id": str(MODEL_ID),
                "goal": "形成月度销售经营复盘",
                "audience": "销售管理层",
                "must_include": ["销售额"],
                "must_exclude": [],
            },
        )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["revision"] == 1
    assert response.json()["content"]["module"] == "ppt"
    assert len(generation.calls) == 1
    access_token, command, trace_id = generation.calls[0]
    assert access_token == "access-token"
    assert command.asset_ids == (ASSET_ID,)
    assert trace_id == "trace-api-brief"


async def test_brief_api_checks_bearer_before_service_availability() -> None:
    app = create_app(
        settings=Settings(),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=FakeSessions()),
        brief_services=None,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/skills")

    assert response.status_code == 401
    assert response.json()["error"]["error_code"] == "session_invalid"


async def test_brief_api_uses_stable_error_envelope() -> None:
    class FailingGeneration(FakeBriefGeneration):
        async def generate(self, access_token: str, command, *, trace_id: str):
            raise BriefOperationError(
                "context_budget_exceeded",
                "所需 evidence 超出模型 Context 预算",
                422,
            )

    async with AsyncClient(
        transport=ASGITransport(app=build_app(generation=FailingGeneration())),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/briefs/generate",
            headers={"Authorization": "Bearer access-token"},
            json={
                "project_id": str(PROJECT_ID),
                "asset_ids": [str(ASSET_ID)],
                "term_library_versions": [],
                "skill_codes": ["ppt.sales-business-review.v1"],
                "model_id": str(MODEL_ID),
                "goal": "形成月度销售经营复盘",
                "audience": "销售管理层",
                "must_include": [],
                "must_exclude": [],
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "context_budget_exceeded"


async def test_brief_generate_api_rejects_unknown_fields() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=build_app()),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/briefs/generate",
            headers={"Authorization": "Bearer access-token"},
            json={
                "project_id": str(PROJECT_ID),
                "asset_ids": [str(ASSET_ID)],
                "term_library_versions": [],
                "skill_codes": ["ppt.sales-business-review.v1"],
                "model_id": str(MODEL_ID),
                "goal": "形成月度销售经营复盘",
                "audience": "销售管理层",
                "must_include": [],
                "must_exclude": [],
                "unexpected": "value",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "validation_error"
