"""Policy-inspected terminal command runner with Emergency Stop process termination."""

from __future__ import annotations

from pathlib import Path
import subprocess
import threading
from typing import Any

from aspirant.security.audit import AuditLogger
from aspirant.security.command_policy import ApprovalQueue, inspect_command
from aspirant.security.permissions import Permission, PermissionManager


class TerminalRunner:
    """Executes inspected PowerShell/shell commands within safety boundaries."""

    def __init__(
        self,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
        approvals: ApprovalQueue,
    ) -> None:
        self.permissions = permissions
        self.audit_logger = audit_logger
        self.approvals = approvals
        self._lock = threading.Lock()
        self._active_procs: set[subprocess.Popen[str]] = set()
        self.permissions.register_stop_hook(self.kill_all_running)

    def kill_all_running(self) -> None:
        with self._lock:
            procs = list(self._active_procs)
        for p in procs:
            try:
                p.kill()
            except Exception:
                pass

    def run(
        self,
        command: str,
        cwd: str | None = None,
        approval_id: str | None = None,
        timeout_sec: int = 30,
    ) -> dict[str, Any]:
        verdict = inspect_command(command)
        if verdict.verdict == "block":
            self.audit_logger.log(
                category="terminal",
                action=f"Blocked command: {command[:120]}",
                permission="EXECUTE",
                decision="blocked",
                status="blocked",
                details={"rule": verdict.matched_rule, "reason": verdict.reason},
            )
            raise PermissionError(f"Blocked by command policy ({verdict.matched_rule}): {verdict.reason}")

        self.permissions.require(Permission.EXECUTE, f"Inspect terminal command: {command[:80]}", category="terminal")

        if verdict.verdict == "require_approval":
            if not approval_id:
                req = self.approvals.request(
                    category="terminal",
                    action="execute_command",
                    target=command,
                    reason=verdict.reason,
                    rollback_hint="Review command effects manually; avoid destructive writes.",
                    payload={"command": command, "cwd": cwd or ""},
                )
                return {
                    "status": "approval_required",
                    "approval": req.to_dict(),
                    "verdict": verdict.reason,
                }
            consumed = self.approvals.consume_approved(approval_id, expected_action="execute_command")
            if consumed is None or consumed.target != command:
                raise PermissionError("Valid matching approval_id is required to execute this command.")

        work_dir = str(Path(cwd).expanduser().resolve()) if cwd else None
        bounded_timeout = max(1, min(timeout_sec, 60))

        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", command],
            cwd=work_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        with self._lock:
            self._active_procs.add(proc)
        try:
            stdout, stderr = proc.communicate(timeout=bounded_timeout)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            rc = -1
        finally:
            with self._lock:
                self._active_procs.discard(proc)

        self.audit_logger.log(
            category="terminal",
            action=f"Executed command (exit={rc}): {command[:90]}",
            permission="EXECUTE",
            decision="executed",
            status="ok" if rc == 0 else "error",
        )
        return {
            "status": "completed",
            "returncode": rc,
            "stdout": stdout[:40_000],
            "stderr": stderr[:15_000],
        }
