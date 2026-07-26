from uuid import UUID
import re

import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from app.models.file_assets import FileAsset
from app.models.projects import Project


def test_asset_models_use_uuid7_and_fixed_table_names() -> None:
    project = Project()
    asset = FileAsset()

    assert project.__tablename__ == "projects"
    assert asset.__tablename__ == "file_assets"
    assert isinstance(project.id, UUID) and project.id.version == 7
    assert isinstance(asset.id, UUID) and asset.id.version == 7


def test_asset_models_use_mysql_binary_uuid_microseconds_and_chinese_comments() -> None:
    ddl = "\n".join(
        str(CreateTable(model.__table__).compile(dialect=mysql.dialect()))
        for model in (Project, FileAsset)
    )

    assert "BINARY(16)" in ddl
    assert "DATETIME(6)" in ddl
    for model in (Project, FileAsset):
        assert model.__table__.comment
        assert re.search(r"[\u4e00-\u9fff]", model.__table__.comment)
        for column in model.__table__.columns:
            assert column.comment, f"{model.__tablename__}.{column.name} 缺少注释"
            assert re.search(r"[\u4e00-\u9fff]", column.comment)


def test_asset_constraints_fix_ownership_storage_and_upload_idempotency() -> None:
    project_fks = {fk.name for fk in Project.__table__.foreign_keys}
    asset_fks = {fk.name for fk in FileAsset.__table__.foreign_keys}
    asset_constraints = {
        constraint.name for constraint in FileAsset.__table__.constraints
    }

    assert project_fks == {"fk_projects_user"}
    assert {
        "fk_file_assets_user",
        "fk_file_assets_project",
        "fk_file_assets_parent",
    } <= asset_fks
    assert "uq_file_assets_storage_location" in asset_constraints
    assert "uq_file_assets_user_idempotency" in asset_constraints


def test_mysql_storage_locator_unique_key_uses_ascii_binary_columns() -> None:
    for column_name in ("storage_provider", "storage_key"):
        column_type = FileAsset.__table__.c[column_name].type.dialect_impl(
            mysql.dialect()
        )
        assert column_type.charset == "ascii"
        assert column_type.collation == "ascii_bin"


def test_project_constraints_allow_only_one_active_default_per_user() -> None:
    project_constraints = {
        constraint.name for constraint in Project.__table__.constraints
    }

    assert "uq_projects_active_default_owner" in project_constraints


async def test_storage_location_and_user_idempotency_are_unique(
    session_factory,
) -> None:
    project = Project(user_id=UUID("019f0000-0000-7000-8000-000000000001"), name="A")
    first = FileAsset(
        user_id=project.user_id,
        project_id=project.id,
        original_filename="report.pdf",
        file_category="document",
        mime_type="application/pdf",
        byte_size=4,
        sha256="a" * 64,
        storage_provider="local",
        storage_key=f"users/{project.user_id}/quarantine/first/original.pdf",
        processing_status="quarantined",
        idempotency_key="upload-1",
    )
    duplicate = FileAsset(
        user_id=project.user_id,
        project_id=project.id,
        original_filename="other.pdf",
        file_category="document",
        mime_type="application/pdf",
        byte_size=4,
        sha256="b" * 64,
        storage_provider="local",
        storage_key=f"users/{project.user_id}/quarantine/second/original.pdf",
        processing_status="quarantined",
        idempotency_key="upload-1",
    )

    async with session_factory() as session:
        session.add_all((project, first))
        await session.commit()
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_active_default_project_is_unique_per_user(session_factory) -> None:
    user_id = UUID("019f0000-0000-7000-8000-000000000001")
    first = Project(user_id=user_id, name="默认项目", is_default=True)
    duplicate = Project(user_id=user_id, name="另一个默认项目", is_default=True)

    async with session_factory() as session:
        session.add(first)
        await session.commit()
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            await session.commit()
