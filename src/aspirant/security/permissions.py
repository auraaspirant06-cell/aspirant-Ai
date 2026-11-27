"""Role-based permission engine, Restricted Mode, and Emergency Kill Switch."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
import threading
from typing import Callable

from aspirant.core.events import EventBus
from aspirant.memory.database import open_sqlite
from aspirant.security.audit import AuditLogger


class Permission(StrEnum):
    """Granular capability permissions enforced across all Aspirant modules."""

    READ = "READ"
    WRITE = "WRITE"
    EXECUTE = "EXECUTE"
    BROWSER = "BROWSER"
    ADMIN = "ADMIN"
    NETWORK = "NETWORK"


DEFAULT_PERMISSIONS: dict[Permission, bool] = {
    Permission.READ: True,
    Permission.WRITE: False,
    Permission.EXECUTE: False,
    Permission.BROWSER: False,
    Permission.ADMIN: False,
    Permission.NETWORK: True,
}

RESTRICTED_BLOCKED_PERMISSIONS = frozenset(
    {Permission.WRITE, Permission.EXECUTE, Permission.BROWSER, Permission.ADMIN}
)


class PermissionDeniedError(PermissionError):
    """Raised when an operation lacks required authorization or safety clearance."""

    def __init__(self, permission: Permission, reason: str) -> None:
        self.permission = permission
        self.reason = reason
        super().__init__(f"Permission {permission.value} denied: {reason}")


class PermissionManager:
    """Thread-safe permission state, Restricted Mode toggle, and Emergency Stop hub."""

    def __init__(
        self,
        audit_db_path: Path,
        audit_logger: AuditLogger,
        event_bus: EventBus | None = None,
        initial_restricted_mode: bool = False,
    ) -> None:
        self.audit_db_path = audit_db_path
        self.audit_logger = audit_logger
        self.event_bus = event_bus
        self._lock = threading.Lock()
        self._permissions: dict[Permission, bool] = dict(DEFAULT_PERMISSIONS)
        self._restricted_mode = initial_restricted_mode
        self._emergency_stop = threading.Event()
        self._stop_hooks: list[Callable[[], None]] = []
        self._load_persisted_state()

    def _load_persisted_state(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with open_sqlite(self.audit_db_path) as conn:
            rows = conn.execute(
                "SELECT permission, granted FROM permission_state"
            ).fetchall()
            existing = {row["permission"]: bool(row["granted"]) for row in rows}
            for perm, default_val in DEFAULT_PERMISSIONS.items():
                if perm.value in existing:
                    self._permissions[perm] = existing[perm.value]
                else:
                    conn.execute(
                        """
                        INSERT INTO permission_state (permission, granted, updated_at, updated_by)
                        VALUES (?, ?, ?, ?)
                        """,
                        (perm.value, int(default_val), now, "system_init"),
                    )

            flag_row = conn.execute(
                "SELECT value FROM runtime_flags WHERE key = 'restricted_mode'"
            ).fetchone()
            if flag_row is not None:
                self._restricted_mode = flag_row["value"] == "1"
            else:
                conn.execute(
                    """
                    INSERT INTO runtime_flags (key, value, updated_at)
                    VALUES ('restricted_mode', ?, ?)
                    """,
                    ("1" if self._restricted_mode else "0", now),
                )

    def snapshot(self) -> dict[str, object]:
        """Return current permission flags and safety mode states."""
        with self._lock:
            return {
                "permissions": {p.value: self._permissions[p] for p in Permission},
                "restricted_mode": self._restricted_mode,
                "emergency_stop_active": self._emergency_stop.is_set(),
            }

    def is_allowed(self, permission: Permission) -> bool:
        """Check whether a permission is currently active without raising."""
        with self._lock:
            if self._emergency_stop.is_set():
                return False
            if self._restricted_mode and permission in RESTRICTED_BLOCKED_PERMISSIONS:
                return False
            return self._permissions.get(permission, False)

    def require(
        self,
        permission: Permission,
        action: str,
        category: str = "security",
        require_explicit_admin: bool = True,
    ) -> None:
        """Verify authorization for an action or raise PermissionDeniedError."""
        with self._lock:
            if self._emergency_stop.is_set():
                reason = "Emergency STOP is active. Resume system before running tasks."
                self._deny(category, action, permission, reason)
            if self._restricted_mode and permission in RESTRICTED_BLOCKED_PERMISSIONS:
                reason = "Restricted Mode blocks system/file/browser/admin modifications."
                self._deny(category, action, permission, reason)
            if not self._permissions.get(permission, False):
                reason = f"Permission {permission.value} is currently disabled."
                self._deny(category, action, permission, reason)
            if permission == Permission.ADMIN and require_explicit_admin:
                # Admin actions must go through an explicit per-action approval flow.
                reason = "ADMIN actions always require explicit per-action approval."
                self._deny(category, action, permission, reason)

        self.audit_logger.log(
            category=category,
            action=action,
            permission=permission.value,
            decision="allowed",
            status="ok",
        )

    def _deny(
        self, category: str, action: str, permission: Permission, reason: str
    ) -> None:
        self.audit_logger.log(
            category=category,
            action=action,
            permission=permission.value,
            decision="denied",
            status="blocked",
            details={"reason": reason},
        )
        raise PermissionDeniedError(permission, reason)

    def set_permission(
        self, permission: Permission, granted: bool, actor: str = "user"
    ) -> dict[str, object]:
        """Update a permission toggle and persist it to SQLite."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._permissions[permission] = bool(granted)

        with open_sqlite(self.audit_db_path) as conn:
            conn.execute(
                """
                INSERT INTO permission_state (permission, granted, updated_at, updated_by)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(permission) DO UPDATE SET
                    granted = excluded.granted,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (permission.value, int(granted), now, actor),
            )

        self.audit_logger.log(
            category="permissions",
            action=f"{'Enable' if granted else 'Disable'} {permission.value}",
            permission=permission.value,
            decision="updated",
            status="ok",
            details={"actor": actor, "granted": granted},
        )
        state = self.snapshot()
        if self.event_bus is not None:
            self.event_bus.publish("security.permissions_updated", state)
        return state

    def set_restricted_mode(self, enabled: bool, actor: str = "user") -> dict[str, object]:
        """Enable or disable Restricted Mode (blocks WRITE, EXECUTE, BROWSER, ADMIN)."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._restricted_mode = bool(enabled)

        with open_sqlite(self.audit_db_path) as conn:
            conn.execute(
                """
                INSERT INTO runtime_flags (key, value, updated_at)
                VALUES ('restricted_mode', ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                ("1" if enabled else "0", now),
            )

        self.audit_logger.log(
            category="security",
            action=f"{'Enable' if enabled else 'Disable'} Restricted Mode",
            permission=Permission.ADMIN.value,
            decision="updated",
            status="ok",
            details={"actor": actor, "restricted_mode": enabled},
        )
        state = self.snapshot()
        if self.event_bus is not None:
            self.event_bus.publish("security.restricted_mode_updated", state)
        return state

    def register_stop_hook(self, hook: Callable[[], None]) -> None:
        """Register a cancellation callback invoked on Emergency STOP."""
        with self._lock:
            self._stop_hooks.append(hook)

    def trigger_emergency_stop(self, reason: str = "User triggered Emergency STOP") -> dict[str, object]:
        """Immediately halt active operations and lock execution capabilities."""
        with self._lock:
            self._emergency_stop.set()
            hooks = list(self._stop_hooks)

        hook_errors: list[str] = []
        for hook in hooks:
            try:
                hook()
            except Exception as exc:  # pragma: no cover - defensive cleanup
                hook_errors.append(str(exc))

        self.audit_logger.log(
            category="emergency",
            action="EMERGENCY STOP TRIGGERED",
            permission=Permission.EXECUTE.value,
            decision="halted",
            status="stopped",
            details={"reason": reason, "hook_errors": hook_errors},
        )
        state = self.snapshot()
        if self.event_bus is not None:
            self.event_bus.publish("security.emergency_stop", {"reason": reason, **state})
        return state

    def resume_from_emergency_stop(self, actor: str = "user") -> dict[str, object]:
        """Clear Emergency STOP lock after explicit user confirmation."""
        with self._lock:
            self._emergency_stop.clear()

        self.audit_logger.log(
            category="emergency",
            action="System resumed from Emergency STOP",
            permission=Permission.EXECUTE.value,
            decision="resumed",
            status="ok",
            details={"actor": actor},
        )
        state = self.snapshot()
        if self.event_bus is not None:
            self.event_bus.publish("security.resumed", state)
        return state

    @property
    def is_emergency_stopped(self) -> bool:
        return self._emergency_stop.is_set()
