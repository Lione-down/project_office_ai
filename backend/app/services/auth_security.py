from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
import jwt
from jwt import InvalidTokenError


class AccessTokenInvalidError(ValueError):
    pass


class AccessTokenExpiredError(AccessTokenInvalidError):
    pass


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: str
    session_id: str


class PasswordService:
    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError):
            return False


class RefreshTokenService:
    def issue(self) -> str:
        return secrets.token_urlsafe(48)

    def hash(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def matches(self, token: str, token_hash: str) -> bool:
        return hmac.compare_digest(self.hash(token), token_hash)


class InviteCodeHasher:
    def __init__(self, pepper: str) -> None:
        self._pepper = pepper.encode("utf-8")

    @staticmethod
    def normalize(code: str) -> str:
        return code.strip().upper()

    def hash(self, code: str) -> str:
        normalized = self.normalize(code).encode("utf-8")
        return hmac.new(self._pepper, normalized, hashlib.sha256).hexdigest()

    def prefix(self, code: str) -> str:
        return self.normalize(code)[:4]


class TokenCodec:
    def __init__(self, secret: str, access_ttl: timedelta) -> None:
        self._secret = secret
        self._access_ttl = access_ttl

    def issue_access_token(
        self, user_id: str, session_id: str, now: datetime | None = None
    ) -> str:
        issued_at = now or datetime.now(UTC)
        payload = {
            "sub": user_id,
            "sid": session_id,
            "iat": int(issued_at.timestamp()),
            "exp": int((issued_at + self._access_ttl).timestamp()),
            "typ": "access",
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def decode_access_token(
        self, token: str, now: datetime | None = None
    ) -> AccessTokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
        except InvalidTokenError as exception:
            raise AccessTokenInvalidError("invalid access token") from exception

        current_time = now or datetime.now(UTC)
        expires_at = payload.get("exp")
        if not isinstance(expires_at, int) or current_time.timestamp() >= expires_at:
            raise AccessTokenExpiredError("access token expired")
        if payload.get("typ") != "access":
            raise AccessTokenInvalidError("invalid token type")
        user_id = payload.get("sub")
        session_id = payload.get("sid")
        if not isinstance(user_id, str) or not isinstance(session_id, str):
            raise AccessTokenInvalidError("invalid access token claims")
        return AccessTokenClaims(user_id=user_id, session_id=session_id)
