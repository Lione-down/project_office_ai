"""Validate the frozen Post-Alpha Agnes chat and PPT studio documentation contract."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILES = {
    "plan": ROOT / "docs" / "PLAN.md",
    "api": ROOT / "docs" / "API.md",
    "data": ROOT / "docs" / "DATA_MODEL.md",
    "security": ROOT / "docs" / "SECURITY.md",
    "environment": ROOT / "docs" / "ENVIRONMENT.md",
}

REQUIRED_BY_FILE = {
    "plan": (
        "post-alpha-contract.v1",
        "P5-001 Contract Gate",
        "chat-sse.v1",
        "deck-brief.v1",
        "agnes-2.5-flash",
        "agnes-2.0-flash",
        "provider_uncertain",
        "P5-002",
        "P5-008",
        "公共 Web 搜索",
    ),
    "api": (
        "post-alpha-contract.v1",
        "`/chat/threads`",
        "`/chat/threads/{thread_id}/export`",
        "`/chat/threads/{thread_id}/messages:stream`",
        "`/chat/runs/{run_id}/stream`",
        "`/chat/runs/{run_id}/cancel`",
        "`/chat/messages/{message_id}/deck-drafts`",
        "`/deck-drafts/{draft_id}`",
        "`/deck-drafts/{draft_id}/confirm`",
        "`/deck-drafts/{draft_id}/preflight`",
        "`/deck-drafts/{draft_id}/media/images`",
        "`/deck-drafts/{draft_id}/media/videos`",
        "`/deck-drafts/{draft_id}/generations`",
        "chat-sse.v1",
        "message.snapshot",
        "cancelled_partial",
        "provider_uncertain",
        "Last-Event-ID",
        "Cache-Control: private, no-store",
        "Idempotency-Key",
    ),
    "data": (
        "post-alpha-contract.v1",
        "`chat_threads`",
        "`chat_messages`",
        "`chat_runs`",
        "`chat_tool_invocations`",
        "`deck_drafts`",
        "`deck_draft_revisions`",
        "`deck_draft_inputs`",
        "`media_jobs`",
        "`media_job_inputs`",
        "deck-brief.v1",
        "cancelled_partial",
        "provider_uncertain",
        "additive migration",
        "31 张",
    ),
    "security": (
        "post-alpha-contract.v1",
        "365 天",
        "30 天",
        "24 小时",
        "彻底删除",
        "DOMPurify",
        "javascript:",
        "Prompt injection",
        "白名单工具",
        "高风险",
        "SSE",
        "Data URI",
        "公共 Web 搜索",
        "public URL",
        "provider_calls",
    ),
    "environment": (
        "post-alpha-contract.v1",
        "OFFICE_AI_CHAT_MAX_INPUT_CHARS",
        "OFFICE_AI_CHAT_MAX_OUTPUT_TOKENS",
        "OFFICE_AI_CHAT_STREAM_TIMEOUT_SECONDS",
        "OFFICE_AI_CHAT_HEARTBEAT_SECONDS",
        "OFFICE_AI_CHAT_MAX_ACTIVE_RUNS_PER_USER",
        "OFFICE_AI_CHAT_RUNS_PER_HOUR",
        "OFFICE_AI_CHAT_RUNS_PER_DAY",
        "OFFICE_AI_CHAT_THREAD_RETENTION_DAYS",
        "OFFICE_AI_CHAT_SOFT_DELETE_GRACE_DAYS",
        "OFFICE_AI_CHAT_BACKUP_RETENTION_DAYS",
        "OFFICE_AI_CHAT_FILE_CONTEXT_MODE",
        "OFFICE_AI_CHAT_THINKING_DEFAULT_ENABLED",
        "OFFICE_AI_CHAT_WEB_SEARCH_ENABLED",
        "OFFICE_AI_DECK_MAX_SLIDES",
        "OFFICE_AI_MEDIA_MAX_ACTIVE_JOBS_PER_USER",
        "OFFICE_AI_MEDIA_PUBLIC_URL_INPUT_ENABLED",
        "OFFICE_AI_VIDEO_EMBED_ENABLED",
        "OFFICE_AI_RUN_REAL_AGNES_CHAT_CONTRACT",
        "OFFICE_AI_RUN_REAL_AGNES_IMAGE_CONTRACT",
        "OFFICE_AI_RUN_REAL_AGNES_VIDEO_CONTRACT",
    ),
}

ENDPOINT_PATHS = (
    "/chat/threads",
    "/chat/threads/{thread_id}",
    "/chat/threads/{thread_id}/export",
    "/chat/threads/{thread_id}/purge",
    "/chat/threads/{thread_id}/messages:stream",
    "/chat/runs/{run_id}/stream",
    "/chat/runs/{run_id}/cancel",
    "/chat/messages/{message_id}/deck-drafts",
    "/deck-drafts/{draft_id}",
    "/deck-drafts/{draft_id}/confirm",
    "/deck-drafts/{draft_id}/preflight",
    "/deck-drafts/{draft_id}/media/images",
    "/deck-drafts/{draft_id}/media/videos",
    "/deck-drafts/{draft_id}/generations",
)

STATE_GROUPS = {
    "chat run": (
        "queued",
        "streaming",
        "succeeded",
        "failed",
        "cancelled_partial",
        "provider_uncertain",
    ),
    "deck draft": (
        "draft",
        "editing",
        "confirmed",
        "preflight",
        "needs_resolution",
        "ready",
        "generation_queued",
    ),
    "media job": (
        "queued",
        "submitted",
        "running",
        "succeeded",
        "failed",
        "provider_uncertain",
        "cancelled",
    ),
}

LOCAL_LINK = re.compile(r"\[[^\]]+\]\((?!https?://|#|mailto:)([^)]+)\)")
ENV_FILE = re.compile(r"(^|/)[^/]*(?:\.env|\.ene)(?:\.|$)", re.IGNORECASE)


def read_utf8(path: Path, failures: list[str]) -> str:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        failures.append(f"{path.relative_to(ROOT)}: cannot read: {exc}")
        return ""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        failures.append(f"{path.relative_to(ROOT)}: UTF-16 BOM is forbidden")
        return ""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        failures.append(f"{path.relative_to(ROOT)}: not strict UTF-8: {exc}")
        return ""


def validate_required_fragments(documents: dict[str, str], failures: list[str]) -> None:
    for key, fragments in REQUIRED_BY_FILE.items():
        for fragment in fragments:
            if fragment not in documents[key]:
                failures.append(
                    f"{CONTRACT_FILES[key].relative_to(ROOT)}: missing {fragment!r}"
                )


def validate_cross_document_alignment(
    documents: dict[str, str], failures: list[str]
) -> None:
    plan_api_data = "\n".join((documents["plan"], documents["api"], documents["data"]))
    for endpoint in ENDPOINT_PATHS:
        if endpoint not in documents["api"]:
            failures.append(f"API endpoint missing: {endpoint}")
    for group, states in STATE_GROUPS.items():
        for state in states:
            if state not in plan_api_data:
                failures.append(
                    f"{group} state missing across PLAN/API/DATA_MODEL: {state}"
                )

    decisions = {
        "file context deck-only": "deck_only",
        "Thinking default disabled": "默认关闭",
        "Web search disabled": "OFFICE_AI_CHAT_WEB_SEARCH_ENABLED=false",
        "public media URL disabled": "OFFICE_AI_MEDIA_PUBLIC_URL_INPUT_ENABLED=false",
        "video embedding disabled": "OFFICE_AI_VIDEO_EMBED_ENABLED=false",
        "three frozen templates": "ppt.executive-blue.v1",
        "high-risk explicit confirmation": "high_risk_confirmation_required",
    }
    all_docs = "\n".join(documents.values())
    for decision, marker in decisions.items():
        if marker not in all_docs:
            failures.append(f"pending decision is not frozen ({decision}): {marker!r}")


def validate_local_links(documents: dict[str, str], failures: list[str]) -> None:
    for key, content in documents.items():
        source = CONTRACT_FILES[key]
        for match in LOCAL_LINK.finditer(content):
            target_text = match.group(1).split("#", 1)[0].strip()
            if not target_text:
                continue
            target = (source.parent / target_text).resolve()
            if not target.exists():
                failures.append(
                    f"{source.relative_to(ROOT)}: broken local link {match.group(1)!r}"
                )


def validate_git_paths(failures: list[str]) -> None:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        failures.append("git ls-files failed")
        return
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8", errors="replace").replace("\\", "/")
        if ENV_FILE.search(path):
            failures.append(f"tracked environment-like file is forbidden: {path}")


def main() -> int:
    failures: list[str] = []
    documents = {key: read_utf8(path, failures) for key, path in CONTRACT_FILES.items()}
    validate_required_fragments(documents, failures)
    validate_cross_document_alignment(documents, failures)
    validate_local_links(documents, failures)
    validate_git_paths(failures)

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        print(f"Post-Alpha contract validation failed: {len(failures)} issue(s).")
        return 1

    print(
        "Post-Alpha contract validation passed: "
        "5 documents, 14 endpoints, 3 state machines, 8 pending decisions."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
