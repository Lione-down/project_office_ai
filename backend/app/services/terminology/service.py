from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.base import new_uuid7
from app.models.projects import Project
from app.models.term_items import TermItem
from app.models.term_libraries import TermLibrary
from app.services.auth_sessions import AuthSessionService
from app.services.terminology.contracts import (
    TermItemSummary,
    TermLibrarySnapshot,
    TermRule,
)
from app.services.terminology.errors import TerminologyOperationError
from app.services.terminology.validation import (
    item_fields,
    library_fields,
    term_key,
)


_UNSET = object()


class TerminologyLibraryService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions

    async def create_library(
        self,
        access_token: str,
        *,
        name: str,
        description: str | None,
        project_id: UUID | None,
    ) -> TermLibrarySnapshot:
        user = await self._sessions.authenticate_access(access_token)
        fields = library_fields(name=name, description=description)
        stable_id = new_uuid7()
        async with self._session_factory() as session, session.begin():
            if project_id is not None:
                await self._owned_project(session, user.user_id, project_id)
            library = TermLibrary(
                id=stable_id,
                library_id=stable_id,
                user_id=user.user_id,
                project_id=project_id,
                name=fields["name"],
                description=fields["description"],
                status="active",
                version=1,
            )
            session.add(library)
            await session.flush()
            return self._snapshot(library, ())

    async def list_libraries(self, access_token: str) -> list[TermLibrarySnapshot]:
        user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            latest = (
                select(
                    TermLibrary.library_id,
                    func.max(TermLibrary.version).label("latest_version"),
                )
                .where(TermLibrary.user_id == user.user_id)
                .group_by(TermLibrary.library_id)
                .subquery()
            )
            libraries = list(
                await session.scalars(
                    select(TermLibrary)
                    .join(
                        latest,
                        and_(
                            TermLibrary.library_id == latest.c.library_id,
                            TermLibrary.version == latest.c.latest_version,
                        ),
                    )
                    .where(TermLibrary.status == "active")
                    .order_by(TermLibrary.created_at, TermLibrary.library_id)
                )
            )
            return [
                self._snapshot(library, await self._items(session, library.id))
                for library in libraries
            ]

    async def get_library(
        self,
        access_token: str,
        library_id: UUID,
        *,
        version: int | None = None,
    ) -> TermLibrarySnapshot:
        user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            library = await self._library(
                session,
                user.user_id,
                library_id,
                version=version,
                require_active=version is None,
            )
            return self._snapshot(library, await self._items(session, library.id))

    async def update_library(
        self,
        access_token: str,
        library_id: UUID,
        changes: dict,
    ) -> TermLibrarySnapshot:
        if not changes or set(changes) - {"name", "description"}:
            raise TerminologyOperationError(
                "term_library_update_invalid", "术语库更新字段无效", 422
            )
        async with self._mutation_context(access_token, library_id) as mutation:
            current, items, session = mutation
            fields = library_fields(
                name=changes.get("name", current.name),
                description=changes.get("description", current.description),
            )
            return await self._fork(
                session,
                current,
                items,
                name=fields["name"],
                description=fields["description"],
            )

    async def delete_library(self, access_token: str, library_id: UUID) -> None:
        async with self._mutation_context(access_token, library_id) as mutation:
            current, _, session = mutation
            await self._fork(session, current, (), status="deleted")

    async def create_item(
        self,
        access_token: str,
        library_id: UUID,
        **values,
    ) -> TermLibrarySnapshot:
        item = item_fields(values)
        async with self._mutation_context(access_token, library_id) as mutation:
            current, items, session = mutation
            self._ensure_canonical_available(items, item["canonical_term"])
            new_item = TermItem(item_id=new_uuid7(), **item)
            return await self._fork(session, current, (*items, new_item))

    async def update_item(
        self,
        access_token: str,
        library_id: UUID,
        item_id: UUID,
        changes: dict,
    ) -> TermLibrarySnapshot:
        allowed = {
            "canonical_term",
            "aliases",
            "unit",
            "definition",
            "metric_scope",
            "priority",
        }
        if not changes or set(changes) - allowed:
            raise TerminologyOperationError(
                "term_item_update_invalid", "术语条目更新字段无效", 422
            )
        async with self._mutation_context(access_token, library_id) as mutation:
            current, items, session = mutation
            existing = next((item for item in items if item.item_id == item_id), None)
            if existing is None:
                raise TerminologyOperationError(
                    "term_item_not_found", "术语条目不存在", 404
                )
            fields = item_fields(
                {
                    "canonical_term": changes.get(
                        "canonical_term", existing.canonical_term
                    ),
                    "aliases": changes.get("aliases", tuple(existing.aliases)),
                    "unit": changes.get("unit", existing.unit),
                    "definition": changes.get("definition", existing.definition),
                    "metric_scope": changes.get("metric_scope", existing.metric_scope),
                    "priority": changes.get("priority", existing.priority),
                }
            )
            self._ensure_canonical_available(
                items, fields["canonical_term"], excluding=item_id
            )
            replacements = tuple(
                TermItem(item_id=item.item_id, **fields)
                if item.item_id == item_id
                else item
                for item in items
            )
            return await self._fork(session, current, replacements)

    async def delete_item(
        self,
        access_token: str,
        library_id: UUID,
        item_id: UUID,
    ) -> TermLibrarySnapshot:
        async with self._mutation_context(access_token, library_id) as mutation:
            current, items, session = mutation
            if not any(item.item_id == item_id for item in items):
                raise TerminologyOperationError(
                    "term_item_not_found", "术语条目不存在", 404
                )
            return await self._fork(
                session,
                current,
                tuple(item for item in items if item.item_id != item_id),
            )

    async def list_rules(
        self,
        access_token: str,
        *,
        project_id: UUID | None,
    ) -> tuple[TermRule, ...]:
        user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            if project_id is not None:
                await self._owned_project(session, user.user_id, project_id)
            latest = (
                select(
                    TermLibrary.library_id,
                    func.max(TermLibrary.version).label("latest_version"),
                )
                .where(TermLibrary.user_id == user.user_id)
                .group_by(TermLibrary.library_id)
                .subquery()
            )
            libraries = list(
                await session.scalars(
                    select(TermLibrary)
                    .join(
                        latest,
                        and_(
                            TermLibrary.library_id == latest.c.library_id,
                            TermLibrary.version == latest.c.latest_version,
                        ),
                    )
                    .where(
                        TermLibrary.status == "active",
                        or_(
                            TermLibrary.project_id.is_(None),
                            TermLibrary.project_id == project_id,
                        ),
                    )
                )
            )
            rules = []
            for library in libraries:
                for item in await self._items(session, library.id):
                    rules.append(
                        TermRule(
                            library_id=library.library_id,
                            library_version=library.version,
                            project_id=library.project_id,
                            canonical_term=item.canonical_term,
                            aliases=tuple(item.aliases),
                            unit=item.unit,
                            metric_scope=item.metric_scope,
                            priority=item.priority,
                        )
                    )
            return tuple(
                sorted(
                    rules,
                    key=lambda rule: (
                        str(rule.project_id or ""),
                        -rule.priority,
                        rule.canonical_term,
                        str(rule.library_id),
                    ),
                )
            )

    @asynccontextmanager
    async def _mutation_context(self, access_token: str, library_id: UUID):
        user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session, session.begin():
            current = await self._library(
                session,
                user.user_id,
                library_id,
                require_active=True,
                for_update=True,
            )
            items = await self._items(session, current.id)
            yield current, items, session

    async def _fork(
        self,
        session: AsyncSession,
        current: TermLibrary,
        items: tuple[TermItem, ...],
        *,
        name: str | object = _UNSET,
        description: str | None | object = _UNSET,
        status: str = "active",
    ) -> TermLibrarySnapshot:
        next_version = TermLibrary(
            library_id=current.library_id,
            user_id=current.user_id,
            project_id=current.project_id,
            previous_version_id=current.id,
            name=current.name if name is _UNSET else name,
            description=current.description if description is _UNSET else description,
            status=status,
            version=current.version + 1,
        )
        session.add(next_version)
        await session.flush()
        cloned = []
        if status == "active":
            for item in items:
                clone = TermItem(
                    item_id=item.item_id,
                    term_library_version_id=next_version.id,
                    canonical_term=item.canonical_term,
                    aliases=list(item.aliases),
                    unit=item.unit,
                    definition=item.definition,
                    metric_scope=item.metric_scope,
                    priority=item.priority,
                )
                session.add(clone)
                cloned.append(clone)
            await session.flush()
        return self._snapshot(next_version, tuple(cloned))

    async def _library(
        self,
        session: AsyncSession,
        user_id: UUID,
        library_id: UUID,
        *,
        version: int | None = None,
        require_active: bool,
        for_update: bool = False,
    ) -> TermLibrary:
        statement = select(TermLibrary).where(
            TermLibrary.user_id == user_id,
            TermLibrary.library_id == library_id,
        )
        if version is None:
            statement = statement.order_by(TermLibrary.version.desc()).limit(1)
        else:
            statement = statement.where(TermLibrary.version == version)
        if for_update:
            statement = statement.with_for_update()
        library = await session.scalar(statement)
        if library is None or (require_active and library.status != "active"):
            raise TerminologyOperationError(
                "term_library_not_found", "术语库不存在", 404
            )
        return library

    @staticmethod
    async def _items(
        session: AsyncSession, library_version_id: UUID
    ) -> tuple[TermItem, ...]:
        return tuple(
            await session.scalars(
                select(TermItem)
                .where(TermItem.term_library_version_id == library_version_id)
                .order_by(TermItem.priority.desc(), TermItem.item_id)
            )
        )

    @staticmethod
    async def _owned_project(
        session: AsyncSession, user_id: UUID, project_id: UUID
    ) -> Project:
        project = await session.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
                Project.deleted_at.is_(None),
            )
        )
        if project is None:
            raise TerminologyOperationError("project_not_found", "项目不存在", 404)
        return project

    @staticmethod
    def _ensure_canonical_available(
        items: tuple[TermItem, ...],
        canonical_term: str,
        *,
        excluding: UUID | None = None,
    ) -> None:
        key = term_key(canonical_term)
        if any(
            item.item_id != excluding and term_key(item.canonical_term) == key
            for item in items
        ):
            raise TerminologyOperationError("term_item_conflict", "标准术语已存在", 409)

    @staticmethod
    def _snapshot(
        library: TermLibrary, items: tuple[TermItem, ...]
    ) -> TermLibrarySnapshot:
        return TermLibrarySnapshot(
            library_id=library.library_id,
            project_id=library.project_id,
            name=library.name,
            description=library.description,
            status=library.status,
            version=library.version,
            created_at=library.created_at,
            items=tuple(
                TermItemSummary(
                    item_id=item.item_id,
                    canonical_term=item.canonical_term,
                    aliases=tuple(item.aliases),
                    unit=item.unit,
                    definition=item.definition,
                    metric_scope=item.metric_scope,
                    priority=item.priority,
                )
                for item in items
            ),
        )
