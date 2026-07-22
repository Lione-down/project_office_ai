from datetime import UTC, datetime, timedelta

import pytest

from app.services.auth_security import (
    AccessTokenExpiredError,
    InviteCodeHasher,
    PasswordService,
    RefreshTokenService,
    TokenCodec,
)


def test_passwords_use_argon2id_and_verify_without_storing_plaintext() -> None:
    passwords = PasswordService()

    password_hash = passwords.hash("correct-horse-battery-staple")

    assert password_hash.startswith("$argon2id$")
    assert "correct-horse-battery-staple" not in password_hash
    assert passwords.verify(password_hash, "correct-horse-battery-staple") is True
    assert passwords.verify(password_hash, "wrong-password") is False


def test_refresh_tokens_are_random_and_only_match_their_sha256_hash() -> None:
    refresh_tokens = RefreshTokenService()

    first_token = refresh_tokens.issue()
    second_token = refresh_tokens.issue()
    first_hash = refresh_tokens.hash(first_token)

    assert first_token != second_token
    assert first_token not in first_hash
    assert refresh_tokens.matches(first_token, first_hash) is True
    assert refresh_tokens.matches(second_token, first_hash) is False


def test_invite_codes_use_a_peppered_hash_and_normalized_input() -> None:
    invite_codes = InviteCodeHasher("test-session-secret-with-enough-entropy")

    invite_hash = invite_codes.hash(" alpha-2026 ")

    assert invite_hash == invite_codes.hash("ALPHA-2026")
    assert "ALPHA-2026" not in invite_hash
    assert invite_codes.prefix(" alpha-2026 ") == "ALPH"


def test_access_tokens_are_signed_and_expiry_is_enforced() -> None:
    now = datetime(2026, 7, 22, 1, 0, tzinfo=UTC)
    tokens = TokenCodec(
        secret="test-session-secret-with-enough-entropy",
        access_ttl=timedelta(minutes=15),
    )

    token = tokens.issue_access_token(
        user_id="019f0000-0000-7000-8000-000000000001",
        session_id="019f0000-0000-7000-8000-000000000002",
        now=now,
    )
    claims = tokens.decode_access_token(token, now=now + timedelta(minutes=14))

    assert claims.user_id == "019f0000-0000-7000-8000-000000000001"
    assert claims.session_id == "019f0000-0000-7000-8000-000000000002"

    with pytest.raises(AccessTokenExpiredError):
        tokens.decode_access_token(token, now=now + timedelta(minutes=16))
