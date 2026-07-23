from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderCreateRequest(StrictModel):
    vendor: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    protocol: str = Field(min_length=1, max_length=64)
    base_url: str = Field(min_length=8, max_length=512)
    default_timeout_seconds: int = Field(default=120, ge=1, le=600)
    config: dict = Field(default_factory=dict)


class ProviderUpdateRequest(StrictModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    protocol: str | None = Field(default=None, min_length=1, max_length=64)
    base_url: str | None = Field(default=None, min_length=8, max_length=512)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")
    default_timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    config: dict | None = None


class ProviderResponse(StrictModel):
    provider_id: UUID
    vendor: str
    display_name: str
    protocol: str
    base_url: str
    status: str
    default_timeout_seconds: int
    config: dict


class CredentialCreateRequest(StrictModel):
    provider_id: UUID
    name: str = Field(min_length=1, max_length=128)
    api_key: SecretStr = Field(min_length=1, max_length=8192)
    rpm_limit: int = Field(ge=1)
    tpm_limit: int = Field(ge=1)
    max_concurrency: int = Field(ge=1)
    rotation_source: str = Field(min_length=1, max_length=64)

    @field_validator("api_key")
    @classmethod
    def api_key_must_not_be_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("credential key must not be blank")
        return value


class CredentialResponse(StrictModel):
    credential_id: UUID
    provider_id: UUID
    name: str
    masked_key: str
    status: str
    rpm_limit: int
    tpm_limit: int
    max_concurrency: int
    rotation_source: str


class CredentialAdminResponse(CredentialResponse):
    last_test_status: str | None


class CredentialUpdateRequest(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: str | None = Field(default=None, pattern="^(active|inactive|suspended)$")
    rpm_limit: int | None = Field(default=None, ge=1)
    tpm_limit: int | None = Field(default=None, ge=1)
    max_concurrency: int | None = Field(default=None, ge=1)


class SensitiveOperationRequest(StrictModel):
    reason: str = Field(max_length=500)


class CredentialRevealRequest(SensitiveOperationRequest):
    current_password: SecretStr = Field(min_length=1, max_length=128)


class CredentialRevealResponse(StrictModel):
    credential_id: UUID
    api_key: str


class CredentialTestResponse(StrictModel):
    credential_id: UUID
    status: str
    retryable: bool
    uncertain: bool


class ModelCreateRequest(StrictModel):
    provider_id: UUID
    credential_id: UUID
    model_code: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)
    capabilities: dict = Field(default_factory=dict)
    context_window: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    user_visible: bool = False
    is_recommended: bool = False
    credit_multiplier: Decimal = Field(default=Decimal("1.0000"), gt=0)
    allowed_skills: list[str] = Field(default_factory=list)


class ModelUpdateRequest(StrictModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    capabilities: dict | None = None
    context_window: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    user_visible: bool | None = None
    is_recommended: bool | None = None
    credit_multiplier: Decimal | None = Field(default=None, gt=0)
    allowed_skills: list[str] | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class ModelResponse(StrictModel):
    model_id: UUID
    provider_id: UUID
    credential_id: UUID
    model_code: str
    display_name: str
    capabilities: dict
    context_window: int
    max_output_tokens: int
    user_visible: bool
    is_recommended: bool
    credit_multiplier: Decimal
    allowed_skills: list[str]
    status: str
