from uuid import UUID

import pytest
from sqlalchemy import select

from app.models.projects import Project
from app.models.term_items import TermItem
from app.models.term_libraries import TermLibrary
from app.services.auth_registration import AuthOperationError
from app.services.auth_sessions import CurrentUser
from app.services.terminology.service import (
    TerminologyLibraryService,
    TerminologyOperationError,
)


USER_A_ID = UUID("019f2000-0000-7000-8000-000000000001")
USER_B_ID = UUID("019f2000-0000-7000-8000-000000000002")
PROJECT_A_ID = UUID("019f2000-0000-7000-8000-000000000003")
PROJECT_B_ID = UUID("019f2000-0000-7000-8000-000000000004")


class FakeSessions:
    async def authenticate_access(self, access_token: str) -> CurrentUser:
        users = {"token-a": USER_A_ID, "token-b": USER_B_ID}
        user_id = users.get(access_token)
        if user_id is None:
            raise AuthOperationError("session_invalid", "Session 已失效", 401)
        return CurrentUser(
            user_id=user_id,
            phone_country_code="+86",
            phone_number="13800000000",
            role="user",
            status="active",
            credit_balance=0,
            must_change_password=False,
        )


async def seed_projects(session_factory) -> None:
    async with session_factory() as session, session.begin():
        session.add_all(
            (
                Project(
                    id=PROJECT_A_ID,
                    user_id=USER_A_ID,
                    name="A 项目",
                    is_default=False,
                    is_archived=False,
                ),
                Project(
                    id=PROJECT_B_ID,
                    user_id=USER_B_ID,
                    name="B 项目",
                    is_default=False,
                    is_archived=False,
                ),
            )
        )


def build_service(session_factory) -> TerminologyLibraryService:
    return TerminologyLibraryService(session_factory, FakeSessions())


async def test_library_crud_is_owner_scoped(session_factory) -> None:
    service = build_service(session_factory)
    created = await service.create_library(
        "token-a", name="销售口径", description="个人销售术语", project_id=None
    )

    assert created.version == 1
    assert created.status == "active"
    assert [item.library_id for item in await service.list_libraries("token-a")] == [
        created.library_id
    ]
    assert await service.list_libraries("token-b") == []

    with pytest.raises(TerminologyOperationError) as error:
        await service.get_library("token-b", created.library_id)

    assert error.value.error_code == "term_library_not_found"


async def test_library_and_item_mutations_create_immutable_versions(
    session_factory,
) -> None:
    service = build_service(session_factory)
    created = await service.create_library(
        "token-a", name="销售口径", description=None, project_id=None
    )
    with_item = await service.create_item(
        "token-a",
        created.library_id,
        canonical_term="销售额",
        aliases=("营收", "收入"),
        unit="CNY",
        definition="确认收入",
        metric_scope="含税销售额",
        priority=10,
    )
    item_id = with_item.items[0].item_id
    updated = await service.update_item(
        "token-a",
        created.library_id,
        item_id,
        {"aliases": ("营业收入",), "priority": 20},
    )
    renamed = await service.update_library(
        "token-a", created.library_id, {"name": "销售指标口径"}
    )

    version_two = await service.get_library("token-a", created.library_id, version=2)
    version_three = await service.get_library("token-a", created.library_id, version=3)

    assert with_item.version == 2
    assert updated.version == 3
    assert renamed.version == 4
    assert version_two.items[0].aliases == ("营收", "收入")
    assert version_two.items[0].priority == 10
    assert version_three.items[0].aliases == ("营业收入",)
    assert version_three.items[0].priority == 20
    assert renamed.name == "销售指标口径"

    async with session_factory() as session:
        versions = list(
            await session.scalars(
                select(TermLibrary)
                .where(TermLibrary.library_id == created.library_id)
                .order_by(TermLibrary.version)
            )
        )
        item_rows = list(await session.scalars(select(TermItem)))

    assert [item.version for item in versions] == [1, 2, 3, 4]
    assert len(item_rows) == 3


async def test_item_delete_only_changes_the_new_snapshot(session_factory) -> None:
    service = build_service(session_factory)
    created = await service.create_library(
        "token-a", name="销售口径", description=None, project_id=None
    )
    with_item = await service.create_item(
        "token-a",
        created.library_id,
        canonical_term="销量",
        aliases=(),
        unit="COUNT_ITEM",
        definition=None,
        metric_scope=None,
        priority=0,
    )

    deleted = await service.delete_item(
        "token-a", created.library_id, with_item.items[0].item_id
    )
    prior = await service.get_library("token-a", created.library_id, version=2)

    assert deleted.version == 3
    assert deleted.items == ()
    assert len(prior.items) == 1


async def test_library_delete_creates_tombstone_and_preserves_history(
    session_factory,
) -> None:
    service = build_service(session_factory)
    created = await service.create_library(
        "token-a", name="销售口径", description=None, project_id=None
    )

    await service.delete_library("token-a", created.library_id)

    assert await service.list_libraries("token-a") == []
    with pytest.raises(TerminologyOperationError) as error:
        await service.get_library("token-a", created.library_id)
    historical = await service.get_library("token-a", created.library_id, version=1)

    assert error.value.error_code == "term_library_not_found"
    assert historical.status == "active"


async def test_project_library_requires_an_owned_active_project(
    session_factory,
) -> None:
    await seed_projects(session_factory)
    service = build_service(session_factory)

    created = await service.create_library(
        "token-a",
        name="A 项目口径",
        description=None,
        project_id=PROJECT_A_ID,
    )

    assert created.project_id == PROJECT_A_ID
    with pytest.raises(TerminologyOperationError) as error:
        await service.create_library(
            "token-a",
            name="越权项目口径",
            description=None,
            project_id=PROJECT_B_ID,
        )
    assert error.value.error_code == "project_not_found"


async def test_rule_listing_uses_latest_active_owner_snapshots(
    session_factory,
) -> None:
    await seed_projects(session_factory)
    service = build_service(session_factory)
    global_library = await service.create_library(
        "token-a", name="全局", description=None, project_id=None
    )
    project_library = await service.create_library(
        "token-a", name="项目", description=None, project_id=PROJECT_A_ID
    )
    await service.create_item(
        "token-a",
        global_library.library_id,
        canonical_term="销售额",
        aliases=("营收",),
        unit="CNY",
        definition=None,
        metric_scope="含税",
        priority=10,
    )
    await service.create_item(
        "token-a",
        project_library.library_id,
        canonical_term="净销售额",
        aliases=("营收",),
        unit="CNY",
        definition=None,
        metric_scope="扣除退款",
        priority=1,
    )

    rules = await service.list_rules("token-a", project_id=PROJECT_A_ID)

    assert {rule.canonical_term for rule in rules} == {"销售额", "净销售额"}
    assert {rule.library_version for rule in rules} == {2}
    assert all(
        rule.library_id in {global_library.library_id, project_library.library_id}
        for rule in rules
    )
