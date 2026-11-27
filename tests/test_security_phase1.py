"""Phase 1 tests for permissions, restricted mode, emergency stop, audit scrubbing, and DPAPI tokens."""

from __future__ import annotations

from pathlib import Path

import pytest

from aspirant.core.events import EventBus
from aspirant.memory.database import DatabaseInitializer
from aspirant.security.audit import AuditLogger, scrub_sensitive_text
from aspirant.security.permissions import (
    Permission,
    PermissionDeniedError,
    PermissionManager,
)
from aspirant.security.tokens import (
    is_allowed_host,
    is_allowed_origin,
    load_or_create_api_token,
)


def _make_security(tmp_path: Path) -> tuple[PermissionManager, AuditLogger]:
    mem_db = tmp_path / "memory.db"
    audit_db = tmp_path / "audit.db"
    DatabaseInitializer(mem_db, audit_db).initialize()
    bus = EventBus()
    logger = AuditLogger(audit_db, event_bus=bus)
    mgr = PermissionManager(audit_db, logger, event_bus=bus)
    return mgr, logger


def test_default_permissions_and_admin_explicit_gate(tmp_path: Path) -> None:
    mgr, _ = _make_security(tmp_path)
    mgr.require(Permission.READ, "read sample config")
    with pytest.raises(PermissionDeniedError):
        mgr.require(Permission.WRITE, "write sample file")

    mgr.set_permission(Permission.ADMIN, True)
    # Even when ADMIN is enabled, explicit per-action flag is still enforced by default.
    with pytest.raises(PermissionDeniedError):
        mgr.require(Permission.ADMIN, "elevated change")

    mgr.require(Permission.ADMIN, "approved elevated change", require_explicit_admin=False)


def test_restricted_mode_blocks_mutating_permissions(tmp_path: Path) -> None:
    mgr, _ = _make_security(tmp_path)
    mgr.set_permission(Permission.WRITE, True)
    mgr.set_permission(Permission.EXECUTE, True)
    mgr.set_permission(Permission.BROWSER, True)

    mgr.set_restricted_mode(True)
    assert mgr.is_allowed(Permission.READ) is True
    assert mgr.is_allowed(Permission.NETWORK) is True
    for blocked in (Permission.WRITE, Permission.EXECUTE, Permission.BROWSER, Permission.ADMIN):
        assert mgr.is_allowed(blocked) is False
        with pytest.raises(PermissionDeniedError):
            mgr.require(blocked, f"attempt {blocked.value}")

    mgr.set_restricted_mode(False)
    mgr.require(Permission.WRITE, "write after unrestrict")


def test_emergency_stop_runs_hooks_and_blocks_until_resumed(tmp_path: Path) -> None:
    mgr, logger = _make_security(tmp_path)
    hook_called = []
    mgr.register_stop_hook(lambda: hook_called.append("stopped"))

    mgr.trigger_emergency_stop("Unit test halt")
    assert hook_called == ["stopped"]
    assert mgr.is_emergency_stopped is True
    with pytest.raises(PermissionDeniedError):
        mgr.require(Permission.READ, "read during emergency stop")

    mgr.resume_from_emergency_stop()
    assert mgr.is_emergency_stopped is False
    mgr.require(Permission.READ, "read after resume")

    logs = logger.recent(limit=10)
    actions = [item["action"] for item in logs]
    assert "EMERGENCY STOP TRIGGERED" in actions
    assert "System resumed from Emergency STOP" in actions


def test_audit_scrubs_secrets_and_national_ids(tmp_path: Path) -> None:
    _, logger = _make_security(tmp_path)
    raw = "Aadhaar 1234 5678 9012 PAN ABCDE1234F key AIzaSyD1234567890abcdefghij12345"
    scrubbed = scrub_sensitive_text(raw)
    assert "1234 5678 9012" not in scrubbed
    assert "ABCDE1234F" not in scrubbed
    assert "AIzaSy" not in scrubbed

    entry = logger.log(
        category="security",
        action=f"Check {raw}",
        permission="READ",
        decision="allowed",
        details={"api_key": "sk-secret1234567890abcdefghij", "note": raw},
    )
    assert entry["details"]["api_key"] == "[REDACTED]"
    assert "1234 5678 9012" not in entry["action"]


def test_dpapi_token_roundtrip_and_host_origin_guards(tmp_path: Path) -> None:
    token_file = tmp_path / ".api_token"
    first = load_or_create_api_token(token_file)
    second = load_or_create_api_token(token_file)
    assert len(first) >= 32
    assert first == second

    assert is_allowed_host("127.0.0.1:8420") is True
    assert is_allowed_host("localhost:8420") is True
    assert is_allowed_host("evil.example.com") is False

    assert is_allowed_origin(None) is True
    assert is_allowed_origin("http://127.0.0.1:8420") is True
    assert is_allowed_origin("https://evil.example.com") is False
