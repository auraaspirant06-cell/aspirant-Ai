"""Safe SSH/PEM deployment configuration validator (never logs or leaks private key contents)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import shutil
from typing import Any


_HOST_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


@dataclass(frozen=True, slots=True)
class SSHConfigCheck:
    host: str
    user: str
    key_path_configured: bool
    key_file_exists: bool
    ssh_client_available: bool
    ready: bool
    issues: list[str]
    preview_command: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_ssh_readiness(
    *,
    host: str,
    user: str = "ubuntu",
    key_path: str = "",
) -> dict[str, Any]:
    """Validate SSH host/user/key file metadata safely without reading or exposing private keys."""
    issues: list[str] = []
    clean_host = host.strip()
    clean_user = user.strip() or "ubuntu"

    if not clean_host or not _HOST_RE.match(clean_host):
        issues.append("Valid SSH_HOST hostname or IP is required.")
    if not _HOST_RE.match(clean_user):
        issues.append("SSH_USER contains invalid characters.")

    key_configured = bool(key_path.strip())
    key_exists = False
    resolved_key_name = "<SSH_KEY_PATH>"
    if key_configured:
        kp = Path(key_path.strip()).expanduser()
        key_exists = kp.is_file()
        resolved_key_name = str(kp.name)
        if not key_exists:
            issues.append(f"PEM/SSH key file not found on disk: {kp.name}")
    else:
        issues.append("SSH_KEY_PATH is not configured.")

    has_ssh = bool(shutil.which("ssh"))
    if not has_ssh:
        issues.append("OpenSSH client (`ssh`) not detected on PATH.")

    ready = len(issues) == 0
    cmd = f"ssh -i <SSH_KEY_PATH:{resolved_key_name}> -o StrictHostKeyChecking=accept-new {clean_user}@{clean_host or '<SSH_HOST>'}"
    return SSHConfigCheck(
        host=clean_host,
        user=clean_user,
        key_path_configured=key_configured,
        key_file_exists=key_exists,
        ssh_client_available=has_ssh,
        ready=ready,
        issues=issues,
        preview_command=cmd,
    ).to_dict()
