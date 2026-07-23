from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from typing import Any


@dataclass(frozen=True)
class AuditContext:
    ip_address: str | None
    user_agent: str | None
    trace_id: str


_SAFE_CONTEXT_KEYS = {
    "amount",
    "backup_retention_days",
    "credential_name",
    "file_category",
    "from_status",
    "idempotency_key",
    "owner_user_id",
    "processing_status",
    "test_status",
    "to_status",
}


def summarize_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = ip_address(value)
    except ValueError:
        return None
    if parsed.version == 4:
        octets = str(parsed).split(".")
        return f"{'.'.join(octets[:3])}.0/24"
    network = ip_network(f"{parsed}/64", strict=False)
    return f"{network.network_address.compressed}/64"


def summarize_user_agent(value: str | None) -> str | None:
    if not value:
        return None
    first_line = value.splitlines()[0].strip()
    return first_line[:160] or None


def redact_audit_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in context.items()
        if key in _SAFE_CONTEXT_KEYS
        and isinstance(value, (str, int, float, bool, type(None)))
    }
