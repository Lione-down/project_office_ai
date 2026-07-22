from uuid import UUID
import re

from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.models.credit_ledger import CreditLedger
from app.models.invite_codes import InviteCode
from app.models.user_sessions import UserSession
from app.models.users import User


def test_auth_models_use_uuid7_identifiers() -> None:
    records = [User(), UserSession(), InviteCode(), CreditLedger()]

    assert all(isinstance(record.id, UUID) for record in records)
    assert all(record.id.version == 7 for record in records)


def test_auth_tables_match_the_fixed_alpha_names() -> None:
    assert User.__tablename__ == "users"
    assert UserSession.__tablename__ == "user_sessions"
    assert InviteCode.__tablename__ == "invite_codes"
    assert CreditLedger.__tablename__ == "credit_ledger"


def test_auth_mysql_schema_uses_binary_uuid_and_microsecond_datetime() -> None:
    ddl = "\n".join(
        str(CreateTable(model.__table__).compile(dialect=mysql.dialect()))
        for model in (User, UserSession, InviteCode, CreditLedger)
    )

    assert "BINARY(16)" in ddl
    assert "DATETIME(6)" in ddl


def test_auth_tables_and_columns_have_chinese_comments() -> None:
    for model in (User, UserSession, InviteCode, CreditLedger):
        assert model.__table__.comment
        assert re.search(r"[\u4e00-\u9fff]", model.__table__.comment)
        for column in model.__table__.columns:
            assert column.comment, f"{model.__tablename__}.{column.name} 缺少注释"
            assert re.search(r"[\u4e00-\u9fff]", column.comment)


def test_auth_model_constraints_match_additive_mysql_migration() -> None:
    invite_constraints = {
        constraint.name for constraint in InviteCode.__table__.constraints
    }
    session_constraints = {
        constraint.name for constraint in UserSession.__table__.constraints
    }
    invite_indexes = {
        index.name: index.unique for index in InviteCode.__table__.indexes
    }
    session_indexes = {
        index.name: index.unique for index in UserSession.__table__.indexes
    }

    assert "uq_invite_codes_code_hash" in invite_constraints
    assert invite_indexes["ix_invite_codes_code_hash"] is False
    assert "uq_user_sessions_refresh_hash" in session_constraints
    assert session_indexes["ix_user_sessions_refresh_token_hash"] is False


def test_auth_cyclic_foreign_keys_are_named_and_deferred() -> None:
    user_invite_fk = next(iter(User.__table__.c.invite_code_id.foreign_keys))
    invite_creator_fk = next(
        iter(InviteCode.__table__.c.created_by_user_id.foreign_keys)
    )

    assert user_invite_fk.name == "fk_users_invite_code"
    assert invite_creator_fk.name == "fk_invite_codes_creator"
    assert invite_creator_fk.use_alter is True

    session_user_fk = next(iter(UserSession.__table__.c.user_id.foreign_keys))
    ledger_user_fk = next(iter(CreditLedger.__table__.c.user_id.foreign_keys))
    ledger_related_fk = next(
        iter(CreditLedger.__table__.c.related_entry_id.foreign_keys)
    )
    assert session_user_fk.name == "fk_sessions_user"
    assert ledger_user_fk.name == "fk_credit_ledger_user"
    assert ledger_related_fk.name == "fk_credit_ledger_related"
