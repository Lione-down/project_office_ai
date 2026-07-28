from collections.abc import Callable
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_providers import AiProvider
from app.models.base import new_uuid7, utc_now
from app.models.chat_messages import ChatMessage
from app.models.chat_runs import ChatRun
from app.models.chat_threads import ChatThread
from app.models.provider_calls import ProviderCall
from app.services.auth_sessions import AuthSessionService
from app.services.chat_contracts import (
    ChatMessageSnapshot,
    ChatOperationError,
    ChatRunCommand,
    ChatThreadCreateCommand,
    ChatThreadDetail,
    ChatThreadSnapshot,
    ChatThreadUpdateCommand,
    PreparedChatStream,
)
from app.services.chat_runtime import ChatRuntime, TERMINAL_RUN_STATUSES
from app.services.chat_requests import (
    chat_request_fingerprint,
    resume_invalid_error,
    safe_chat_title,
    validate_chat_idempotency_key,
)
from app.services.chat_persistence import (
    append_chat_messages,
    chat_message_snapshot,
    chat_thread_snapshot,
    owned_chat_thread,
    resolve_chat_model,
)
from app.services.provider_contracts import build_provider_adapter
from app.services.provider_security import CredentialCipher
from app.services.rate_limit import RateLimitExceeded, RedisRateLimiter
from app.settings.config import Settings


ACTIVE_RUN_STATUSES = {"queued", "streaming"}


class ChatService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
        cipher: CredentialCipher,
        *,
        settings: Settings,
        adapter_factory: Callable[[AiProvider], object] | None = None,
        admission_limiter: RedisRateLimiter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions
        self._settings = settings
        self._admission = admission_limiter
        self._runtime = ChatRuntime(
            session_factory,
            cipher,
            adapter_factory or build_provider_adapter,
            settings,
        )

    async def create_thread(
        self,
        access_token: str,
        command: ChatThreadCreateCommand,
        idempotency_key: str,
    ) -> ChatThreadSnapshot:
        validate_chat_idempotency_key(idempotency_key)
        current_user = await self._sessions.authenticate_access(access_token)
        fingerprint = chat_request_fingerprint(command.model_dump(mode="json"))
        async with self._session_factory() as session, session.begin():
            existing = await session.scalar(
                select(ChatThread).where(
                    ChatThread.user_id == current_user.user_id,
                    ChatThread.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise ChatOperationError(
                        "idempotency_conflict",
                        "Idempotency-Key 已用于不同请求",
                        409,
                    )
                return await chat_thread_snapshot(session, existing)
            model, _, _ = await resolve_chat_model(session, command.model_id)
            now = utc_now()
            thread_id = new_uuid7()
            thread = ChatThread(
                id=thread_id,
                thread_id=thread_id,
                user_id=current_user.user_id,
                title="新对话",
                default_model_id=model.id,
                mode=command.mode,
                status="active",
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                last_activity_at=now,
                retention_expires_at=now
                + timedelta(days=self._settings.chat_thread_retention_days),
                deleted_at=None,
            )
            session.add(thread)
            await session.flush()
            return await chat_thread_snapshot(session, thread)

    async def list_threads(
        self,
        access_token: str,
        search: str | None = None,
    ) -> tuple[ChatThreadSnapshot, ...]:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            statement = select(ChatThread).where(
                ChatThread.user_id == current_user.user_id,
                ChatThread.deleted_at.is_(None),
            )
            normalized_search = (search or "").strip()
            if normalized_search:
                statement = statement.where(
                    ChatThread.title.contains(normalized_search)
                )
            threads = list(
                await session.scalars(
                    statement.order_by(
                        ChatThread.last_activity_at.desc(),
                        ChatThread.id.desc(),
                    ).limit(100)
                )
            )
            return tuple(
                [await chat_thread_snapshot(session, thread) for thread in threads]
            )

    async def get_thread(
        self,
        access_token: str,
        thread_id: UUID,
    ) -> ChatThreadDetail:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            thread = await owned_chat_thread(session, current_user, thread_id)
            messages = list(
                await session.scalars(
                    select(ChatMessage)
                    .where(ChatMessage.thread_id == thread.id)
                    .order_by(ChatMessage.sequence)
                )
            )
            snapshot = await chat_thread_snapshot(session, thread)
            return ChatThreadDetail(
                **snapshot.model_dump(),
                messages=tuple(
                    [
                        await chat_message_snapshot(session, message)
                        for message in messages
                    ]
                ),
            )

    async def update_thread(
        self,
        access_token: str,
        thread_id: UUID,
        command: ChatThreadUpdateCommand,
    ) -> ChatThreadSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session, session.begin():
            thread = await owned_chat_thread(
                session,
                current_user,
                thread_id,
                for_update=True,
            )
            if command.title is not None:
                thread.title = command.title.strip()
            if command.default_model_id is not None:
                model, _, _ = await resolve_chat_model(
                    session,
                    command.default_model_id,
                )
                thread.default_model_id = model.id
            if command.mode is not None:
                thread.mode = command.mode
            thread.updated_at = utc_now()
            return await chat_thread_snapshot(session, thread)

    async def delete_thread(
        self,
        access_token: str,
        thread_id: UUID,
    ) -> None:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session, session.begin():
            thread = await owned_chat_thread(
                session,
                current_user,
                thread_id,
                include_deleted=True,
                for_update=True,
            )
            if thread.deleted_at is None:
                thread.status = "deleted"
                thread.deleted_at = utc_now()

    async def prepare_stream(
        self,
        access_token: str,
        thread_id: UUID,
        command: ChatRunCommand,
        idempotency_key: str,
        *,
        trace_id: str,
    ) -> PreparedChatStream:
        validate_chat_idempotency_key(idempotency_key)
        current_user = await self._sessions.authenticate_access(access_token)
        if command.context_asset_ids:
            raise ChatOperationError(
                "chat_file_context_not_enabled",
                "首期 Chat 不支持文件上下文",
                409,
            )
        if command.content is not None and len(command.content) > (
            self._settings.chat_max_input_chars
        ):
            raise ChatOperationError(
                "chat_request_invalid",
                "消息超过允许长度",
                400,
            )
        fingerprint = chat_request_fingerprint(
            {
                "thread_id": str(thread_id),
                **command.model_dump(mode="json"),
            }
        )
        async with self._session_factory() as session, session.begin():
            existing = await session.scalar(
                select(ChatRun).where(
                    ChatRun.user_id == current_user.user_id,
                    ChatRun.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise ChatOperationError(
                        "idempotency_conflict",
                        "Idempotency-Key 已用于不同请求",
                        409,
                    )
                if existing.status not in TERMINAL_RUN_STATUSES:
                    raise ChatOperationError(
                        "chat_run_not_active",
                        "该请求仍在处理中",
                        409,
                    )
                return PreparedChatStream(
                    run_id=existing.id,
                    events=self._runtime.replay(existing.id, trace_id),
                    replayed=True,
                )
            thread = await owned_chat_thread(
                session,
                current_user,
                thread_id,
                for_update=True,
            )
            model_id = command.model_id or thread.default_model_id
            model, provider, credential = await resolve_chat_model(
                session,
                model_id,
            )
            if (
                command.thinking_enabled
                and model.capabilities.get("thinking") is not True
            ):
                raise ChatOperationError(
                    "chat_thinking_unsupported",
                    "所选模型未发布 Thinking capability",
                    422,
                )
            active_runs = await session.scalar(
                select(func.count(ChatRun.id)).where(
                    ChatRun.user_id == current_user.user_id,
                    ChatRun.status.in_(ACTIVE_RUN_STATUSES),
                )
            )
            if active_runs >= self._settings.chat_max_active_runs_per_user:
                raise ChatOperationError(
                    "chat_concurrency_exceeded",
                    "当前已有进行中的对话",
                    429,
                )
            await self._check_admission(current_user.user_id)
            user_message, assistant_message = await append_chat_messages(
                session,
                thread,
                command,
            )
            run_id = new_uuid7()
            run = ChatRun(
                id=run_id,
                user_id=current_user.user_id,
                thread_id=thread.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                model_id=model.id,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                status="queued",
                last_event_sequence=0,
                last_content_sequence=0,
                provider_snapshot={
                    "provider_id": str(provider.id),
                    "credential_id": str(credential.id),
                    "model_id": str(model.id),
                    "model_code": model.model_code,
                },
                capability_snapshot=dict(model.capabilities),
                pricing_snapshot={
                    "credit_multiplier": str(model.credit_multiplier),
                },
                thinking_enabled=command.thinking_enabled,
                provider_request_id=None,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=0,
                finish_reason=None,
                cancel_requested_at=None,
                error_code=None,
                error_reason=None,
                started_at=None,
                completed_at=None,
            )
            session.add(run)
            await session.flush()
            assistant_message.run_id = run_id
            session.add(
                ProviderCall(
                    brief_group_id=None,
                    brief_revision_id=None,
                    task_id=None,
                    task_step_id=None,
                    chat_run_id=run_id,
                    attempt=1,
                    provider_id=provider.id,
                    model_id=model.id,
                    credential_id=credential.id,
                    provider_request_id=None,
                    status="queued",
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    latency_ms=0,
                    cost_amount=None,
                    error_category=None,
                    is_redacted=True,
                )
            )
            now = utc_now()
            thread.last_activity_at = now
            thread.retention_expires_at = now + timedelta(
                days=self._settings.chat_thread_retention_days
            )
            if thread.title == "新对话" and command.content:
                thread.title = safe_chat_title(command.content)
            await session.flush()
        return PreparedChatStream(
            run_id=run_id,
            events=self._runtime.stream(run_id, trace_id),
            replayed=False,
        )

    async def reconnect_stream(
        self,
        access_token: str,
        run_id: UUID,
        last_event_id: str,
        *,
        trace_id: str,
    ) -> PreparedChatStream:
        current_user = await self._sessions.authenticate_access(access_token)
        expected_prefix = f"{run_id}:"
        if not last_event_id.startswith(expected_prefix):
            raise resume_invalid_error()
        try:
            sequence = int(last_event_id.removeprefix(expected_prefix))
        except ValueError as exception:
            raise resume_invalid_error() from exception
        async with self._session_factory() as session:
            run = await session.scalar(
                select(ChatRun).where(
                    ChatRun.id == run_id,
                    ChatRun.user_id == current_user.user_id,
                )
            )
            if run is None:
                raise ChatOperationError(
                    "chat_run_not_found",
                    "对话运行不存在",
                    404,
                )
            if sequence < 0 or sequence > run.last_event_sequence:
                raise resume_invalid_error()
        return PreparedChatStream(
            run_id=run_id,
            events=self._runtime.replay(
                run_id,
                trace_id,
                after_sequence=sequence,
            ),
            replayed=True,
        )

    async def cancel_run(
        self,
        access_token: str,
        run_id: UUID,
    ) -> ChatMessageSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session, session.begin():
            run = await session.scalar(
                select(ChatRun)
                .where(
                    ChatRun.id == run_id,
                    ChatRun.user_id == current_user.user_id,
                )
                .with_for_update()
            )
            if run is None:
                raise ChatOperationError(
                    "chat_run_not_found",
                    "对话运行不存在",
                    404,
                )
            message = await session.get(ChatMessage, run.assistant_message_id)
            if run.status not in TERMINAL_RUN_STATUSES:
                run.cancel_requested_at = utc_now()
                self._runtime.request_cancel(run.id)
            return await chat_message_snapshot(session, message)

    async def _check_admission(self, user_id: UUID) -> None:
        if self._admission is None:
            raise ChatOperationError(
                "chat_rate_limit_unavailable",
                "对话限流服务不可用",
                503,
            )
        try:
            await self._admission.check(
                "chat-hour",
                str(user_id),
                self._settings.chat_runs_per_hour,
                3600,
            )
            await self._admission.check(
                "chat-day",
                str(user_id),
                self._settings.chat_runs_per_day,
                86_400,
            )
        except RateLimitExceeded as exception:
            raise ChatOperationError(
                "chat_rate_limit_exceeded",
                "对话请求过于频繁，请稍后重试",
                429,
            ) from exception
