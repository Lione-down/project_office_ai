from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated


PhoneNumber = Annotated[str, StringConstraints(pattern=r"^1[3-9]\d{9}$")]
StrongPassword = Annotated[str, StringConstraints(min_length=12, max_length=128)]


class RegisterRequest(BaseModel):
    phone_number: PhoneNumber
    password: StrongPassword
    invite_code: str = Field(min_length=4, max_length=64)
    accepted_terms: Literal[True]


class LoginRequest(BaseModel):
    phone_number: PhoneNumber
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: StrongPassword


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class CurrentUserResponse(BaseModel):
    user_id: UUID
    phone_country_code: str
    phone_number: str
    role: str
    status: str
    credit_balance: int
    must_change_password: bool
