from app.services.audit import redact_audit_context, summarize_ip, summarize_user_agent


def test_audit_network_context_is_bounded_and_redacted() -> None:
    assert summarize_ip("203.0.113.42") == "203.0.113.0/24"
    assert summarize_ip("2001:db8:abcd:12::1") == "2001:db8:abcd:12::/64"
    assert summarize_user_agent("Browser/1.0\nAuthorization: secret") == "Browser/1.0"

    sanitized = redact_audit_context(
        {
            "owner_user_id": "019f0000-0000-7000-8000-000000000902",
            "storage_key": "users/private/original.xlsx",
            "password": "never-store-this",
            "backup_retention_days": 30,
        }
    )
    assert sanitized == {
        "owner_user_id": "019f0000-0000-7000-8000-000000000902",
        "backup_retention_days": 30,
    }
