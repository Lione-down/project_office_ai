from uuid import UUID

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
