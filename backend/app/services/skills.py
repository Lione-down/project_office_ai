from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.skills import Skill
from app.services.auth_sessions import AuthSessionService
from app.services.briefs.service import BriefOperationError
from app.skills.catalog import (
    ALPHA_SKILLS,
    POST_ALPHA_USER_SKILLS,
    SkillDefinition,
    skill_row_matches_definition,
)


class SkillCatalogService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions

    async def list_published(self, access_token: str) -> tuple[SkillDefinition, ...]:
        await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            rows = list(
                await session.scalars(
                    select(Skill)
                    .where(
                        Skill.kind == "user_workflow",
                        Skill.status == "published",
                    )
                    .order_by(Skill.skill_code)
                )
            )
        expected_by_code = {skill.skill_code: skill for skill in POST_ALPHA_USER_SKILLS}
        required_alpha_codes = {skill.skill_code for skill in ALPHA_SKILLS}
        rows_by_code = {row.skill_code: row for row in rows}
        if not required_alpha_codes.issubset(rows_by_code) or not set(
            rows_by_code
        ).issubset(expected_by_code):
            raise BriefOperationError(
                "skill_contract_invalid", "Alpha Skill发布集合无效", 409
            )
        for code, row in rows_by_code.items():
            expected = expected_by_code[code]
            if not skill_row_matches_definition(row, expected):
                raise BriefOperationError(
                    "skill_contract_invalid", "Skill版本合同不可用", 409
                )
        return tuple(
            skill
            for skill in POST_ALPHA_USER_SKILLS
            if skill.skill_code in rows_by_code
        )

    async def get_published(
        self, access_token: str, skill_code: str
    ) -> SkillDefinition:
        skills = await self.list_published(access_token)
        try:
            return next(skill for skill in skills if skill.skill_code == skill_code)
        except StopIteration as exception:
            raise BriefOperationError(
                "skill_not_found", "Skill不存在", 404
            ) from exception
