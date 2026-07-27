from hashlib import sha256
import json
from time import perf_counter
from typing import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_providers import AiProvider
from app.models.briefs import Brief
from app.models.provider_calls import ProviderCall
from app.models.provider_credentials import ProviderCredential
from app.models.base import new_uuid7
from app.providers.agnes import ChatCompletionRequest, ProviderCompletion
from app.services.auth_sessions import AuthSessionService
from app.services.briefs.context import BriefContextError, build_evidence_context
from app.services.briefs.contracts import (
    BriefGenerationCommand,
    BriefRevisionSnapshot,
    StructuredBrief,
)
from app.services.briefs.errors import BriefOperationError
from app.services.briefs.inputs import (
    GenerationInputLoader,
    GenerationInputs,
    expected_snapshot,
)
from app.services.briefs.prompting import (
    enforce_message_budget,
    generation_messages,
    repair_messages,
)
from app.services.briefs.validation import (
    BriefValidationError,
    resolve_brief_evidence_references,
    validate_brief_response,
)
from app.services.evidence.store import EvidenceManifestStore
from app.services.provider_contracts import ProviderAdapter, build_provider_adapter
from app.services.provider_security import (
    CredentialCipher,
    ProviderConfigurationError,
)
from app.services.preflight.catalog import build_alpha_output_plan
from app.skills.catalog import (
    SkillSelectionError,
    resolve_alpha_skill_selection,
)


class BriefGenerationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
        manifest_store: EvidenceManifestStore,
        cipher: CredentialCipher,
        *,
        adapter_factory: Callable[[AiProvider], ProviderAdapter] | None = None,
        fixed_prompt_reserve: int = 2048,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions
        self._input_loader = GenerationInputLoader(session_factory, manifest_store)
        self._cipher = cipher
        self._adapter_factory = adapter_factory or build_provider_adapter
        self._fixed_prompt_reserve = fixed_prompt_reserve

    async def generate(
        self,
        access_token: str,
        command: BriefGenerationCommand,
        *,
        trace_id: str,
    ) -> BriefRevisionSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        try:
            selection = resolve_alpha_skill_selection(command.skill_codes)
        except SkillSelectionError as exception:
            raise BriefOperationError(
                exception.error_code, exception.message, 422
            ) from exception
        inputs = await self._input_loader.load(current_user, command, selection)
        expected = expected_snapshot(inputs, command)
        try:
            context = build_evidence_context(
                inputs.evidence,
                context_window=min(inputs.model.context_window, 262_144),
                max_output_tokens=inputs.model.max_output_tokens,
                fixed_prompt_reserve=self._fixed_prompt_reserve,
            )
        except BriefContextError as exception:
            raise BriefOperationError(
                exception.error_code, exception.message, 422
            ) from exception
        try:
            api_key = self._cipher.decrypt(inputs.credential.encrypted_key)
        except ProviderConfigurationError as exception:
            raise BriefOperationError(
                exception.error_code, exception.message, 503
            ) from exception
        adapter = self._adapter_factory(inputs.provider)
        brief_group_id = new_uuid7()
        messages = generation_messages(
            command, expected, context.serialized, inputs.term_rules
        )
        enforce_message_budget(messages, inputs.model)
        call_ids: list[UUID] = []
        last_validation_error: BriefValidationError | None = None
        for attempt in (1, 2):
            completion, latency_ms = await self._invoke_provider(
                adapter=adapter,
                api_key=api_key,
                messages=messages,
                trace_id=trace_id,
                inputs=inputs,
                brief_group_id=brief_group_id,
                attempt=attempt,
            )
            try:
                resolved_content = resolve_brief_evidence_references(
                    completion.content,
                    dict(context.reference_map),
                )
                brief = validate_brief_response(resolved_content, expected)
            except BriefValidationError as exception:
                last_validation_error = exception
                call_ids.append(
                    await self._record_completion(
                        inputs=inputs,
                        brief_group_id=brief_group_id,
                        attempt=attempt,
                        completion=completion,
                        latency_ms=latency_ms,
                        status="schema_invalid",
                        error_category=exception.error_code,
                    )
                )
                if attempt == 2:
                    raise BriefOperationError(
                        exception.error_code, exception.message, 422
                    ) from exception
                messages = repair_messages(
                    command,
                    expected,
                    context.serialized,
                    inputs.term_rules,
                    completion.content,
                )
                enforce_message_budget(messages, inputs.model)
                continue
            call_ids.append(
                await self._record_completion(
                    inputs=inputs,
                    brief_group_id=brief_group_id,
                    attempt=attempt,
                    completion=completion,
                    latency_ms=latency_ms,
                    status="succeeded",
                    error_category=None,
                )
            )
            return await self._persist_brief(
                inputs=inputs,
                brief_group_id=brief_group_id,
                brief=brief,
                call_ids=tuple(call_ids),
            )
        raise BriefOperationError(
            last_validation_error.error_code
            if last_validation_error
            else "brief_schema_invalid",
            "Structured Brief Schema 无效",
            422,
        )

    async def _invoke_provider(
        self,
        *,
        adapter: ProviderAdapter,
        api_key: str,
        messages: list[dict],
        trace_id: str,
        inputs: GenerationInputs,
        brief_group_id: UUID,
        attempt: int,
    ) -> tuple[ProviderCompletion, int]:
        started = perf_counter()
        try:
            completion = await adapter.create_chat_completion(
                api_key=api_key,
                request=ChatCompletionRequest(
                    model=inputs.model.model_code,
                    messages=messages,
                    tools=[],
                    timeout_seconds=inputs.provider.default_timeout_seconds,
                    max_output_tokens=inputs.model.max_output_tokens,
                    temperature=0,
                    trace_id=trace_id,
                    response_format={"type": "json_object"},
                ),
            )
        except Exception as exception:
            latency_ms = max(0, int((perf_counter() - started) * 1000))
            classified = adapter.classify_error(exception)
            await self._record_failure(
                inputs=inputs,
                brief_group_id=brief_group_id,
                attempt=attempt,
                latency_ms=latency_ms,
                status=("provider_uncertain" if classified.uncertain else "failed"),
                error_category=classified.category,
                pause_credential=classified.disable_credential,
            )
            raise BriefOperationError(
                classified.category,
                (
                    "Provider 调用结果不确定"
                    if classified.uncertain
                    else "Provider 调用失败"
                ),
                409 if classified.uncertain else 502,
            ) from exception
        return completion, max(0, int((perf_counter() - started) * 1000))

    async def _record_completion(
        self,
        *,
        inputs: GenerationInputs,
        brief_group_id: UUID,
        attempt: int,
        completion: ProviderCompletion,
        latency_ms: int,
        status: str,
        error_category: str | None,
    ) -> UUID:
        call = ProviderCall(
            brief_group_id=brief_group_id,
            attempt=attempt,
            provider_id=inputs.provider.id,
            model_id=inputs.model.id,
            credential_id=inputs.credential.id,
            provider_request_id=completion.provider_request_id,
            status=status,
            prompt_tokens=completion.usage.prompt_tokens,
            completion_tokens=completion.usage.completion_tokens,
            total_tokens=completion.usage.total_tokens,
            latency_ms=latency_ms,
            cost_amount=None,
            error_category=error_category,
            is_redacted=True,
        )
        async with self._session_factory() as session, session.begin():
            session.add(call)
        return call.id

    async def _record_failure(
        self,
        *,
        inputs: GenerationInputs,
        brief_group_id: UUID,
        attempt: int,
        latency_ms: int,
        status: str,
        error_category: str,
        pause_credential: bool,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                ProviderCall(
                    brief_group_id=brief_group_id,
                    attempt=attempt,
                    provider_id=inputs.provider.id,
                    model_id=inputs.model.id,
                    credential_id=inputs.credential.id,
                    provider_request_id=None,
                    status=status,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    latency_ms=latency_ms,
                    cost_amount=None,
                    error_category=error_category,
                    is_redacted=True,
                )
            )
            if pause_credential:
                credential = await session.get(ProviderCredential, inputs.credential.id)
                if credential is not None:
                    credential.status = "paused"

    async def _persist_brief(
        self,
        *,
        inputs: GenerationInputs,
        brief_group_id: UUID,
        brief: StructuredBrief,
        call_ids: tuple[UUID, ...],
    ) -> BriefRevisionSnapshot:
        content = brief.model_dump(mode="json")
        canonical = json.dumps(
            content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        content_checksum = sha256(canonical.encode("utf-8")).hexdigest()
        source_snapshot = {
            "module": content["module"],
            "goal": content["goal"],
            "audience": content["audience"],
            "source_asset_versions": content["source_asset_versions"],
            "term_library_versions": content["term_library_versions"],
            "selected_skills": content["selected_skills"],
            "selected_model": content["selected_model"],
            "must_include": content["must_include"],
            "must_exclude": content["must_exclude"],
            "template_versions": [
                {
                    "template_code": output.template_code,
                    "version": output.template_version,
                }
                for output in build_alpha_output_plan(
                    tuple(skill["skill_code"] for skill in content["selected_skills"]),
                    (),
                    inputs.model.credit_multiplier,
                )
            ],
        }
        revision = Brief(
            brief_group_id=brief_group_id,
            revision=1,
            user_id=inputs.current_user.user_id,
            project_id=inputs.project.id,
            selected_model_id=inputs.model.id,
            source_snapshot=source_snapshot,
            content=content,
            content_checksum=content_checksum,
            status="draft",
            confirmed_at=None,
        )
        async with self._session_factory() as session, session.begin():
            session.add(revision)
            await session.flush()
            calls = list(
                await session.scalars(
                    select(ProviderCall).where(ProviderCall.id.in_(call_ids))
                )
            )
            if len(calls) != len(call_ids):
                raise BriefOperationError(
                    "provider_call_audit_incomplete",
                    "Provider调用审计记录不完整",
                    500,
                )
            for call in calls:
                call.brief_revision_id = revision.id
        return BriefRevisionSnapshot(
            brief_id=revision.id,
            brief_group_id=revision.brief_group_id,
            revision=revision.revision,
            status="draft",
            content=brief,
            content_checksum=content_checksum,
        )
