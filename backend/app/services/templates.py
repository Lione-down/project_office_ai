from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.templates import Template
from app.services.auth_sessions import AuthSessionService
from app.services.briefs.service import BriefOperationError
from app.templates.catalog import (
    PRESENTATION_TEMPLATES,
    PresentationTemplateDefinition,
    template_row_matches_definition,
)


class TemplateCatalogService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions

    async def list_published(
        self,
        access_token: str,
        *,
        category: str | None = None,
    ) -> tuple[PresentationTemplateDefinition, ...]:
        await self._sessions.authenticate_access(access_token)
        await self._validate_runtime_rows()
        return tuple(
            item
            for item in PRESENTATION_TEMPLATES
            if category is None or item.category == category
        )

    async def get_published(
        self,
        access_token: str,
        template_code: str,
        *,
        version: str | None = None,
    ) -> PresentationTemplateDefinition:
        templates = await self.list_published(access_token)
        semantic_version = version or "1.0.0"
        try:
            return next(
                item
                for item in templates
                if item.template_code == template_code
                and item.version == semantic_version
            )
        except StopIteration as exception:
            raise BriefOperationError(
                "template_not_found",
                "模板不存在",
                404,
            ) from exception

    async def _validate_runtime_rows(self) -> None:
        async with self._session_factory() as session:
            rows = list(
                await session.scalars(
                    select(Template)
                    .where(
                        Template.owner_user_id.is_(None),
                        Template.source == "system_original",
                        Template.template_type == "pptx",
                        Template.status == "published",
                    )
                    .order_by(Template.sort_order, Template.template_code)
                )
            )
        expected = {
            (item.template_code, item.database_version): item
            for item in PRESENTATION_TEMPLATES
        }
        actual = {(row.template_code, row.version): row for row in rows}
        if set(actual) != set(expected):
            raise BriefOperationError(
                "template_contract_invalid",
                "系统模板发布集合无效",
                409,
            )
        for reference, definition in expected.items():
            row = actual[reference]
            if not template_row_matches_definition(row, definition):
                raise BriefOperationError(
                    "template_contract_invalid",
                    "系统模板版本合同不可用",
                    409,
                )
