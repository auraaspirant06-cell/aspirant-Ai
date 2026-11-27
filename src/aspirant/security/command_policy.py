"""Command inspection, protected path boundaries, and interactive approval queue."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import threading
from typing import Any
import uuid


@dataclass(frozen=True, slots=True)
class CommandVerdict:
    verdict: str       # allow | require_approval | block
    risk: str          # low | medium | high | critical
    reason: str
    matched_rule: str


_BLOCKED_COMMAND_RULES: list[tuple[str, re.Pattern[str], str]] = [
    ("disk_format", re.compile(r"(?i)\b(?:format|diskpart|bcdedit|vssadmin|fdisk|mkfs)\b"), "Disk/partition/boot modification commands are blocked."),
    ("security_tamper", re.compile(r"(?i)\b(?:Set-MpPreference|Add-MpPreference|Remove-MpPreference|netsh\s+advfirewall|WinDefend|Disable-WindowsOptionalFeature)\b"), "Disabling antivirus, Defender, or firewall is blocked."),
    ("encoded_obfuscation", re.compile(r"(?i)(?:powershell(?:\.exe)?\s+.*-(?:enc|encodedcommand)\b|(?:curl|wget|irm|iwr)\b.*\|\s*(?:iex|invoke-expression|sh|bash)\b)"), "Obfuscated or remote-piped script execution is blocked."),
    ("silent_install", re.compile(r"(?i)\b(?:winget|choco|msiexec)\b.*(?:/qn|--silent|/quiet|-s\b)"), "Silent software installation is prohibited."),
    ("registry_delete", re.compile(r"(?i)\b(?:reg\s+delete|Remove-Item\s+HKLM:|Remove-Item\s+HKCU:)\b"), "Registry deletion is blocked."),
    ("privilege_user_mod", re.compile(r"(?i)\b(?:net\s+user|net\s+localgroup|takeown|runas)\b"), "User account or ownership elevation commands are blocked."),
    ("wipe_root", re.compile(r"(?i)\b(?:rm\s+-rf\s+[/\\]|del\s+/s\s+/q\s+C:\\|Remove-Item\s+.*-Recurse.*C:\\(?:Windows|Users|Program))"), "Recursive deletion of root or OS directories is blocked."),
]

_SAFE_READ_PREFIXES = (
    "dir",
    "ls",
    "pwd",
    "echo ",
    "whoami",
    "hostname",
    "get-date",
    "get-location",
    "get-childitem",
    "python --version",
    "node -v",
    "uv --version",
    "git status",
    "git log",
    "git diff",
    "git branch",
)


def inspect_command(command: str) -> CommandVerdict:
    """Inspect a shell command before execution to classify safety and approval requirements."""
    stripped = command.strip()
    if not stripped:
        return CommandVerdict("block", "low", "Command is empty.", "empty_command")

    for rule_name, pattern, reason in _BLOCKED_COMMAND_RULES:
        if pattern.search(stripped):
            return CommandVerdict("block", "critical", reason, rule_name)

    lowered = stripped.lower()
    # Disallow chaining arbitrary commands after a safe read prefix
    has_chain = any(sep in stripped for sep in ("&&", "||", ";", "|", ">", ">>", "`", "$("))
    if not has_chain and any(lowered == p or lowered.startswith(p) for p in _SAFE_READ_PREFIXES):
        return CommandVerdict("allow", "low", "Safe read-only inspection command.", "safe_read_allowlist")

    return CommandVerdict(
        "require_approval",
        "medium",
        "Command falls outside the read-only allowlist and requires explicit user approval.",
        "manual_inspection",
    )


def _protected_prefixes() -> list[Path]:
    prefixes = [
        Path("C:/Windows"),
        Path("C:/Program Files"),
        Path("C:/Program Files (x86)"),
        Path("C:/ProgramData"),
    ]
    home = Path.home()
    prefixes.extend(
        [
            home / ".ssh",
            home / ".gnupg",
            home / ".aws",
            home / ".azure",
        ]
    )
    local_app = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
    prefixes.extend(
        [
            local_app / "Microsoft" / "Edge" / "User Data",
            local_app / "Google" / "Chrome" / "User Data",
        ]
    )
    return [p.resolve() for p in prefixes]


_SENSITIVE_FILENAMES = frozenset({".api_token", "vault.enc", "vault.key", "id_rsa", "id_ed25519", "cookies", "login data"})


def is_protected_path(path: Path) -> tuple[bool, str]:
    """Return (True, reason) if path resides in OS, browser-cookie, SSH, or vault locations."""
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()

    if resolved.name.lower() in _SENSITIVE_FILENAMES:
        return True, f"Protected credential/vault file: {resolved.name}"

    for prefix in _protected_prefixes():
        if resolved == prefix or prefix in resolved.parents:
            return True, f"Protected system or credential directory: {prefix}"

    return False, ""


@dataclass
class ApprovalRequest:
    id: str
    category: str
    action: str
    target: str
    reason: str
    rollback_hint: str
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | approved | denied
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "action": self.action,
            "target": self.target,
            "reason": self.reason,
            "rollback_hint": self.rollback_hint,
            "status": self.status,
            "created_at": self.created_at,
        }


class ApprovalQueue:
    """In-memory explicit user approval gate for risky automation, coding, or gov steps."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, ApprovalRequest] = {}

    def request(
        self,
        category: str,
        action: str,
        target: str,
        reason: str,
        rollback_hint: str,
        payload: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            id=str(uuid.uuid4())[:8],
            category=category,
            action=action,
            target=target,
            reason=reason,
            rollback_hint=rollback_hint,
            payload=dict(payload or {}),
        )
        with self._lock:
            self._items[req.id] = req
        return req

    def list_requests(self, status_filter: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._items.values())
        if status_filter:
            items = [item for item in items if item.status == status_filter]
        return [item.to_dict() for item in reversed(items)]

    def decide(self, approval_id: str, approve: bool) -> ApprovalRequest | None:
        with self._lock:
            req = self._items.get(approval_id)
            if req is None:
                return None
            req.status = "approved" if approve else "denied"
            return req

    def consume_approved(self, approval_id: str, expected_action: str | None = None) -> ApprovalRequest | None:
        """Verify and consume an approved token once so approvals cannot be replayed."""
        with self._lock:
            req = self._items.get(approval_id)
            if req is None or req.status != "approved":
                return None
            if expected_action and req.action != expected_action:
                return None
            req.status = "consumed"
            return req
