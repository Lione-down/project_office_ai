from hashlib import sha256
import json
import re

from app.services.chat_contracts import ChatOperationError


IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


def validate_chat_idempotency_key(value: str) -> None:
    if IDEMPOTENCY_PATTERN.fullmatch(value) is None:
        raise ChatOperationError(
            "chat_request_invalid",
            "Idempotency-Key 无效",
            400,
        )


def chat_request_fingerprint(payload: dict) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def safe_chat_title(content: str) -> str:
    normalized = " ".join(content.split())
    return normalized[:60] or "新对话"


def resume_invalid_error() -> ChatOperationError:
    return ChatOperationError(
        "chat_stream_resume_invalid",
        "流式重连位置无效",
        409,
    )
