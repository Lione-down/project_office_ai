from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.briefs import Brief
from app.models.provider_credentials import ProviderCredential
from app.services.generation_contracts import GenerationOperationError
from app.services.preflight.contracts import PreflightSnapshot
from app.services.preflight.catalog import template_checksum_for_reference


def build_model_snapshot(model: AiModel, credential: ProviderCredential) -> dict:
    return {
        "model_id": str(model.id),
        "provider_id": str(model.provider_id),
        "credential_id": str(credential.id),
        "model_code": model.model_code,
        "capabilities": model.capabilities,
        "context_window": model.context_window,
        "max_output_tokens": model.max_output_tokens,
        "credit_multiplier": str(model.credit_multiplier),
        "rpm_limit": credential.rpm_limit,
        "tpm_limit": credential.tpm_limit,
        "max_concurrency": credential.max_concurrency,
    }


def validate_runtime_snapshot(
    brief: Brief,
    preflight: PreflightSnapshot,
    model: AiModel,
    credential: ProviderCredential,
    provider: AiProvider | None,
) -> None:
    expected_identity = {
        "model_id": str(model.id),
        "provider_id": str(model.provider_id),
        "credential_id": str(credential.id),
        "model_code": model.model_code,
    }
    selected_skills = {output.skill_code for output in preflight.outputs}
    if (
        brief.source_snapshot.get("selected_model") != expected_identity
        or model.status != "active"
        or provider is None
        or provider.status != "active"
        or credential.provider_id != model.provider_id
        or preflight.credit_multiplier is None
        or str(model.credit_multiplier) != str(preflight.credit_multiplier)
        or not selected_skills.issubset(set(model.allowed_skills))
        or not model.capabilities.get("structured_output", False)
    ):
        raise GenerationOperationError(
            "generation_preflight_stale",
            "模型或费用配置已变化，请重新执行 Preflight",
            409,
        )


def build_skill_snapshot(brief: Brief, preflight: PreflightSnapshot) -> list[dict]:
    versions = {
        item["skill_code"]: item["version"]
        for item in brief.source_snapshot.get("selected_skills", [])
        if "skill_code" in item and "version" in item
    }
    if any(output.skill_code not in versions for output in preflight.outputs):
        raise GenerationOperationError(
            "brief_integrity_failed", "Brief Skill快照不完整", 409
        )
    snapshots = []
    for output in preflight.outputs:
        template_checksum = output.template_checksum or template_checksum_for_reference(
            output.template_code,
            output.template_version,
        )
        if template_checksum is None:
            raise GenerationOperationError(
                "generation_preflight_stale",
                "模板版本配置已变化，请重新执行 Preflight",
                409,
            )
        snapshots.append(
            {
                "skill_code": output.skill_code,
                "version": versions[output.skill_code],
                "kind": output.kind,
                "template_code": output.template_code,
                "template_version": output.template_version,
                "template_checksum": template_checksum,
                "estimated_credits": output.estimated_credits,
            }
        )
    return snapshots
