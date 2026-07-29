from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base, Skill
from app.services.briefs.service import BriefOperationError
from app.services.skills import SkillCatalogService
from app.skills.catalog import (
    ALPHA_SKILLS,
    KNOWLEDGE_EDUCATION_SKILL,
    POST_ALPHA_USER_SKILLS,
)


class FakeSessions:
    async def authenticate_access(self, access_token: str):
        assert access_token == "access-token"
        return object()


@pytest_asyncio.fixture
async def skill_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        session.add_all(
            [
                Skill(
                    skill_code=skill.skill_code,
                    version=skill.version,
                    kind=skill.kind,
                    display_name=skill.display_name,
                    description=skill.description,
                    output_kind=skill.output_kind,
                    input_schema=skill.input_schema,
                    output_schema=skill.output_schema,
                    workflow=skill.workflow,
                    capability_requirements=skill.capability_requirements,
                    status=skill.status,
                    checksum=skill.checksum,
                )
                for skill in ALPHA_SKILLS
            ]
        )
    yield factory
    await engine.dispose()


async def test_skill_catalog_returns_only_checksum_verified_published_versions(
    skill_session_factory,
) -> None:
    service = SkillCatalogService(skill_session_factory, FakeSessions())

    skills = await service.list_published("access-token")
    selected = await service.get_published(
        "access-token", "ppt.sales-business-review.v1"
    )

    assert skills == ALPHA_SKILLS
    assert selected == ALPHA_SKILLS[0]


async def test_skill_catalog_accepts_the_versioned_post_alpha_deck_skill(
    skill_session_factory,
) -> None:
    async with skill_session_factory() as session, session.begin():
        skill = KNOWLEDGE_EDUCATION_SKILL
        session.add(
            Skill(
                skill_code=skill.skill_code,
                version=skill.version,
                kind=skill.kind,
                display_name=skill.display_name,
                description=skill.description,
                output_kind=skill.output_kind,
                input_schema=skill.input_schema,
                output_schema=skill.output_schema,
                workflow=skill.workflow,
                capability_requirements=skill.capability_requirements,
                status=skill.status,
                checksum=skill.checksum,
            )
        )
    service = SkillCatalogService(skill_session_factory, FakeSessions())

    skills = await service.list_published("access-token")
    selected = await service.get_published("access-token", "ppt.knowledge-education.v1")

    assert skills == POST_ALPHA_USER_SKILLS
    assert selected == KNOWLEDGE_EDUCATION_SKILL


async def test_skill_catalog_fails_closed_on_database_contract_drift(
    skill_session_factory,
) -> None:
    async with skill_session_factory() as session, session.begin():
        row = await session.get(
            Skill,
            (
                await session.execute(
                    Skill.__table__.select().where(
                        Skill.skill_code == "ppt.sales-business-review.v1"
                    )
                )
            )
            .first()
            .id,
        )
        row.checksum = "0" * 64
    service = SkillCatalogService(skill_session_factory, FakeSessions())

    with pytest.raises(BriefOperationError) as error:
        await service.list_published("access-token")

    assert error.value.error_code == "skill_contract_invalid"


async def test_skill_catalog_rejects_content_drift_with_unchanged_checksum(
    skill_session_factory,
) -> None:
    async with skill_session_factory() as session, session.begin():
        row = (
            await session.scalars(
                select(Skill).where(Skill.skill_code == "ppt.sales-business-review.v1")
            )
        ).first()
        await session.execute(
            Skill.__table__.update()
            .where(Skill.id == row.id)
            .values(workflow={"steps": ["unreviewed-runtime-drift"]})
        )
    service = SkillCatalogService(skill_session_factory, FakeSessions())

    with pytest.raises(BriefOperationError) as error:
        await service.list_published("access-token")

    assert error.value.error_code == "skill_contract_invalid"
