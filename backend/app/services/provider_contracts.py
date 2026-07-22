from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.provider_credentials import ProviderCredential
from app.providers.agnes import (
    AgnesAdapter,
    ErrorClassification,
    ProviderConfigurationError as AgnesConfigurationError,
)


PROVIDER_UPDATE_FIELDS = frozenset(
    {
        "display_name",
        "protocol",
        "base_url",
        "status",
        "default_timeout_seconds",
        "config",
    }
)
SENSITIVE_CONFIG_KEYS = frozenset(
    {
        "api_key",
        "access_token",
        "refresh_token",
        "password",
        "secret",
        "master_key",
        "authorization",
        "credential",
    }
)


class ProviderOperationError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class CreatedCredential:
    credential_id: UUID
    provider_id: UUID
    name: str
    masked_key: str
    status: str
    rpm_limit: int
    tpm_limit: int
    max_concurrency: int
    rotation_source: str


@dataclass(frozen=True)
class CredentialSummary:
    credential_id: UUID
    provider_id: UUID
    name: str
    masked_key: str
    status: str
    rpm_limit: int
    tpm_limit: int
    max_concurrency: int
    rotation_source: str
    last_test_status: str | None


@dataclass(frozen=True)
class AuditContext:
    ip_address: str | None
    user_agent: str | None
    trace_id: str


@dataclass(frozen=True)
class RevealedCredential:
    credential_id: UUID
    api_key: str


@dataclass(frozen=True)
class ProviderSummary:
    provider_id: UUID
    vendor: str
    display_name: str
    protocol: str
    base_url: str
    status: str
    default_timeout_seconds: int
    config: dict


@dataclass(frozen=True)
class ModelSummary:
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
    allowed_skills: list
    status: str


@dataclass(frozen=True)
class CredentialTestResult:
    credential_id: UUID
    status: str
    retryable: bool
    uncertain: bool


class ProviderAdapter(Protocol):
    async def test_authentication(self, api_key: str) -> bool: ...

    def classify_error(self, error: Exception) -> ErrorClassification: ...


def provider_summary(provider: AiProvider) -> ProviderSummary:
    return ProviderSummary(
        provider_id=provider.id,
        vendor=provider.vendor,
        display_name=provider.display_name,
        protocol=provider.protocol,
        base_url=provider.base_url,
        status=provider.status,
        default_timeout_seconds=provider.default_timeout_seconds,
        config=provider.config,
    )


def model_summary(model: AiModel) -> ModelSummary:
    return ModelSummary(
        model_id=model.id,
        provider_id=model.provider_id,
        credential_id=model.credential_id,
        model_code=model.model_code,
        display_name=model.display_name,
        capabilities=model.capabilities,
        context_window=model.context_window,
        max_output_tokens=model.max_output_tokens,
        user_visible=model.user_visible,
        is_recommended=model.is_recommended,
        credit_multiplier=model.credit_multiplier,
        allowed_skills=model.allowed_skills,
        status=model.status,
    )


def credential_summary(credential: ProviderCredential) -> CredentialSummary:
    return CredentialSummary(
        credential_id=credential.id,
        provider_id=credential.provider_id,
        name=credential.name,
        masked_key="********",
        status=credential.status,
        rpm_limit=credential.rpm_limit,
        tpm_limit=credential.tpm_limit,
        max_concurrency=credential.max_concurrency,
        rotation_source=credential.rotation_source,
        last_test_status=credential.last_test_status,
    )


def mask_key(api_key: str) -> str:
    return f"****{api_key[-4:]}"


def build_provider_adapter(provider: AiProvider) -> ProviderAdapter:
    if provider.vendor != "agnes":
        raise ProviderOperationError(
            "provider_not_certified", "Alpha 仅认证 Agnes Provider", 422
        )
    return AgnesAdapter(
        configuration={
            **provider.config,
            "base_url": provider.base_url,
            "timeout_seconds": provider.default_timeout_seconds,
        }
    )


def validate_provider_configuration(
    vendor: str, base_url: str, timeout_seconds: int, config: dict
) -> None:
    validate_non_sensitive_config(config)
    if vendor != "agnes":
        return
    try:
        AgnesAdapter(
            configuration={
                **config,
                "base_url": base_url,
                "timeout_seconds": timeout_seconds,
            }
        )
    except AgnesConfigurationError as error:
        raise ProviderOperationError(
            "provider_configuration_invalid", error.message, 422
        ) from error


def validate_non_sensitive_config(config: object) -> None:
    pending = [config]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                normalized_key = str(key).strip().lower().replace("-", "_")
                if normalized_key in SENSITIVE_CONFIG_KEYS:
                    raise ProviderOperationError(
                        "provider_config_contains_secret",
                        "Provider 非敏感配置不能包含 Secret 字段",
                        422,
                    )
                pending.append(value)
        elif isinstance(current, list):
            pending.extend(current)


def validate_provider_changes(changes: dict) -> None:
    if unknown := set(changes) - PROVIDER_UPDATE_FIELDS:
        raise ProviderOperationError(
            "provider_update_invalid",
            f"不支持更新 Provider 字段：{', '.join(sorted(unknown))}",
            422,
        )
    if "config" in changes:
        validate_non_sensitive_config(changes["config"])
