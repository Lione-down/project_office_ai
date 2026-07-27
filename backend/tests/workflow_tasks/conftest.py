from dataclasses import dataclass
from uuid import UUID

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.projects import Project
from app.models.users import User
from app.services.auth_sessions import CurrentUser
from app.services.workflow_tasks import WorkflowTaskService


USER_ID = UUID("019fa300-0000-7000-8000-000000000001")
OTHER_USER_ID = UUID("019fa300-0000-7000-8000-000000000002")
PROJECT_ID = UUID("019fa300-0000-7000-8000-000000000011")


class Sessions:
    def __init__(self, current_user: CurrentUser) -> None:
        self.current_user = current_user

    async def authenticate_access(self, _access_token: str) -> CurrentUser:
        return self.current_user


def current_user(user_id: UUID) -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        phone_country_code="+86",
        phone_number="13800000000",
        role="user",
        status="active",
        credit_balance=10_000,
        must_change_password=False,
    )


@dataclass
class WorkflowHarness:
    session_factory: async_sessionmaker
    service: WorkflowTaskService


@pytest_asyncio.fixture
async def workflow_harness(tmp_path) -> WorkflowHarness:
    database_path = tmp_path / "workflow-service.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session, session.begin():
        session.add_all(
            [
                User(
                    id=USER_ID,
                    phone_country_code="+86",
                    phone_number="13800000000",
                    role="user",
                    status="active",
                    password_hash="hash",
                    credit_balance=10_000,
                    must_change_password=False,
                    invite_code_id=None,
                ),
                User(
                    id=OTHER_USER_ID,
                    phone_country_code="+86",
                    phone_number="13900000000",
                    role="user",
                    status="active",
                    password_hash="hash",
                    credit_balance=10_000,
                    must_change_password=False,
                    invite_code_id=None,
                ),
                Project(
                    id=PROJECT_ID,
                    user_id=USER_ID,
                    name="默认项目",
                    is_default=True,
                    is_archived=False,
                    deleted_at=None,
                ),
            ]
        )
    harness = WorkflowHarness(
        session_factory=session_factory,
        service=WorkflowTaskService(
            session_factory,
            Sessions(current_user(USER_ID)),
        ),
    )
    try:
        yield harness
    finally:
        await engine.dispose()
