from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.base import new_uuid7, utc_now
from app.models.chat_messages import ChatMessage
from app.models.chat_runs import ChatRun
from app.models.chat_threads import ChatThread
from app.models.provider_credentials import ProviderCredential
from app.services.auth_sessions import CurrentUser
from app.services.chat_contracts import (
    ChatMessageSnapshot,
    ChatOperationError,
    ChatRunCommand,
    ChatThreadSnapshot,
)


async def append_chat_messages(
    session: AsyncSession,
    thread: ChatThread,
    command: ChatRunCommand,
) -> tuple[ChatMessage, ChatMessage]:
    next_sequence = (
        await session.scalar(
            select(func.max(ChatMessage.sequence)).where(
                ChatMessage.thread_id == thread.id
            )
        )
        or 0
    ) + 1
    if command.regenerate_from_message_id is not None:
        source = await owned_chat_message(
            session,
            thread,
            command.regenerate_from_message_id,
            role="assistant",
        )
        if source.parent_message_id is None:
            raise ChatOperationError(
                "chat_request_invalid",
                "重新生成来源无效",
                400,
            )
        user_message = await session.get(ChatMessage, source.parent_message_id)
        if user_message is None:
            raise ChatOperationError(
                "chat_message_not_found",
                "消息不存在",
                404,
            )
        branch_root = source.branch_root_id
    else:
        parent_id = command.parent_message_id
        supersedes = None
        if command.supersedes_message_id is not None:
            supersedes = await owned_chat_message(
                session,
                thread,
                command.supersedes_message_id,
                role="user",
            )
            parent_id = supersedes.parent_message_id
        elif parent_id is None:
            parent_id = await session.scalar(
                select(ChatMessage.id)
                .where(
                    ChatMessage.thread_id == thread.id,
                    ChatMessage.role == "assistant",
                    ChatMessage.status.in_({"succeeded", "cancelled_partial"}),
                )
                .order_by(ChatMessage.sequence.desc())
                .limit(1)
            )
        if parent_id is not None:
            await owned_chat_message(session, thread, parent_id)
        user_id = new_uuid7()
        branch_root = supersedes.branch_root_id if supersedes else user_id
        user_message = ChatMessage(
            id=user_id,
            thread_id=thread.id,
            sequence=next_sequence,
            role="user",
            content=command.content.strip(),
            content_format="markdown",
            status="succeeded",
            parent_message_id=parent_id,
            supersedes_message_id=(supersedes.id if supersedes is not None else None),
            branch_root_id=branch_root,
            run_id=None,
            provenance_summary={"kind": "user_input"},
            finalized_at=utc_now(),
        )
        session.add(user_message)
        next_sequence += 1
    assistant = ChatMessage(
        id=new_uuid7(),
        thread_id=thread.id,
        sequence=next_sequence,
        role="assistant",
        content="",
        content_format="markdown",
        status="pending",
        parent_message_id=user_message.id,
        supersedes_message_id=None,
        branch_root_id=branch_root,
        run_id=None,
        provenance_summary={"kind": "agnes_inference"},
        finalized_at=None,
    )
    session.add(assistant)
    await session.flush()
    return user_message, assistant


async def owned_chat_thread(
    session: AsyncSession,
    current_user: CurrentUser,
    thread_id: UUID,
    *,
    include_deleted: bool = False,
    for_update: bool = False,
) -> ChatThread:
    statement = select(ChatThread).where(
        ChatThread.thread_id == thread_id,
        ChatThread.user_id == current_user.user_id,
    )
    if not include_deleted:
        statement = statement.where(ChatThread.deleted_at.is_(None))
    if for_update:
        statement = statement.with_for_update()
    thread = await session.scalar(statement)
    if thread is None:
        raise ChatOperationError(
            "chat_thread_not_found",
            "会话不存在",
            404,
        )
    return thread


async def owned_chat_message(
    session: AsyncSession,
    thread: ChatThread,
    message_id: UUID,
    *,
    role: str | None = None,
) -> ChatMessage:
    conditions = [
        ChatMessage.id == message_id,
        ChatMessage.thread_id == thread.id,
    ]
    if role is not None:
        conditions.append(ChatMessage.role == role)
    message = await session.scalar(select(ChatMessage).where(*conditions))
    if message is None:
        raise ChatOperationError(
            "chat_message_not_found",
            "消息不存在",
            404,
        )
    return message


async def resolve_chat_model(
    session: AsyncSession,
    model_id: UUID | None,
) -> tuple[AiModel, AiProvider, ProviderCredential]:
    statement = select(AiModel).where(
        AiModel.status == "active",
        AiModel.user_visible.is_(True),
    )
    if model_id is None:
        statement = statement.where(
            AiModel.model_code == "agnes-2.5-flash",
            AiModel.is_recommended.is_(True),
        )
    else:
        statement = statement.where(AiModel.id == model_id)
    model = await session.scalar(statement)
    if model is None or model.capabilities.get("chat_stream") is not True:
        raise ChatOperationError(
            "chat_model_unavailable",
            "所选 Chat 模型不可用",
            422,
        )
    provider = await session.get(AiProvider, model.provider_id)
    credential = await session.get(ProviderCredential, model.credential_id)
    if (
        provider is None
        or credential is None
        or provider.status != "active"
        or credential.status != "active"
    ):
        raise ChatOperationError(
            "chat_model_unavailable",
            "所选 Chat 模型不可用",
            422,
        )
    return model, provider, credential


async def chat_thread_snapshot(
    session: AsyncSession,
    thread: ChatThread,
) -> ChatThreadSnapshot:
    model = await session.get(AiModel, thread.default_model_id)
    if model is None:
        raise ChatOperationError(
            "chat_model_unavailable",
            "所选 Chat 模型不可用",
            422,
        )
    return ChatThreadSnapshot(
        thread_id=thread.thread_id,
        user_id=thread.user_id,
        title=thread.title,
        default_model_id=thread.default_model_id,
        model_code=model.model_code,
        mode=thread.mode,
        status=thread.status,
        last_activity_at=thread.last_activity_at,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


async def chat_message_snapshot(
    session: AsyncSession,
    message: ChatMessage,
) -> ChatMessageSnapshot:
    model_code = None
    if message.run_id is not None:
        run = await session.get(ChatRun, message.run_id)
        if run is not None:
            model_code = run.provider_snapshot.get("model_code")
    return ChatMessageSnapshot(
        message_id=message.id,
        sequence=message.sequence,
        role=message.role,
        content=message.content,
        status=message.status,
        parent_message_id=message.parent_message_id,
        supersedes_message_id=message.supersedes_message_id,
        branch_root_id=message.branch_root_id,
        run_id=message.run_id,
        model_code=model_code,
        created_at=message.created_at,
        finalized_at=message.finalized_at,
    )
