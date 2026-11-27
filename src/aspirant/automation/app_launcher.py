"""Allowlisted Windows application launcher, safe process closer, and settings shortcuts."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import psutil

from aspirant.security.audit import AuditLogger
from aspirant.security.permissions import Permission, PermissionManager

SAFE_SETTINGS_PAGES: dict[str, str] = {
    "display": "ms-settings:display",
    "sound": "ms-settings:sound",
    "wifi": "ms-settings:network-wifi",
    "bluetooth": "ms-settings:bluetooth",
    "storage": "ms-settings:storagesense",
    "apps": "ms-settings:appsfeatures",
    "privacy_mic": "ms-settings:privacy-microphone",
    "updates": "ms-settings:windowsupdate",
}

CRITICAL_PROTECTED_PROCESSES = frozenset(
    {
        "system",
        "smss.exe",
        "csrss.exe",
        "wininit.exe",
        "winlogon.exe",
        "services.exe",
        "lsass.exe",
        "svchost.exe",
        "explorer.exe",
        "msmpeng.exe",
        "dwm.exe",
    }
)


def _find_edge_path() -> str | None:
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    return next((c for c in candidates if Path(c).exists()), shutil.which("msedge"))


def _find_vscode_path() -> str | None:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    candidates = [
        local / "Programs" / "Microsoft VS Code" / "Code.exe",
        Path(r"C:\Program Files\Microsoft VS Code\Code.exe"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return shutil.which("code")


class AppLauncher:
    """Opens allowlisted apps/settings and safely closes user-launched apps."""

    def __init__(self, permissions: PermissionManager, audit_logger: AuditLogger) -> None:
        self.permissions = permissions
        self.audit_logger = audit_logger

    def catalog(self) -> list[dict[str, Any]]:
        apps = [
            ("edge", "Microsoft Edge", _find_edge_path()),
            ("vscode", "Visual Studio Code", _find_vscode_path()),
            ("terminal", "Windows PowerShell / Terminal", shutil.which("wt") or shutil.which("powershell")),
            ("notepad", "Notepad", shutil.which("notepad")),
            ("calc", "Calculator", shutil.which("calc")),
            ("explorer", "File Explorer", shutil.which("explorer")),
            ("vlc", "VLC Media Player", r"C:\Program Files\VideoLAN\VLC\vlc.exe" if Path(r"C:\Program Files\VideoLAN\VLC\vlc.exe").exists() else shutil.which("vlc")),
        ]
        return [
            {"id": aid, "name": label, "available": bool(exe), "path": exe or ""}
            for aid, label, exe in apps
        ]

    def open_app(self, app_id: str, args: list[str] | None = None) -> dict[str, Any]:
        self.permissions.require(Permission.EXECUTE, f"Launch app '{app_id}'", category="automation")
        entry = next((a for a in self.catalog() if a["id"] == app_id), None)
        if entry is None:
            raise ValueError(f"App '{app_id}' is not in the allowlisted application catalog.")
        if not entry["available"]:
            raise FileNotFoundError(f"App '{entry['name']}' is not installed on this PC.")

        cmd = [entry["path"], *(args or [])]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.audit_logger.log(
            category="automation",
            action=f"Launched {entry['name']} (PID {proc.pid})",
            permission="EXECUTE",
            decision="executed",
            status="ok",
        )
        return {"app": entry["name"], "pid": proc.pid, "launched": True}

    def open_settings_page(self, page_id: str) -> dict[str, Any]:
        self.permissions.require(Permission.EXECUTE, f"Open Windows Settings '{page_id}'", category="automation")
        uri = SAFE_SETTINGS_PAGES.get(page_id)
        if not uri:
            raise ValueError(f"Unknown settings page '{page_id}'.")
        if sys.platform == "win32":
            os.startfile(uri)  # noqa: S606
        return {"page": page_id, "uri": uri, "opened": True}

    def close_app(self, process_name: str) -> dict[str, Any]:
        self.permissions.require(Permission.EXECUTE, f"Close process '{process_name}'", category="automation")
        target = process_name.strip().lower()
        if not target.endswith(".exe"):
            target_exe = f"{target}.exe"
        else:
            target_exe = target
        if target in CRITICAL_PROTECTED_PROCESSES or target_exe in CRITICAL_PROTECTED_PROCESSES or "python" in target:
            raise PermissionError(f"Process '{process_name}' is protected and cannot be closed automatically.")

        terminated = 0
        for proc in psutil.process_iter(["pid", "name"]):
            pname = (proc.info.get("name") or "").lower()
            if pname in {target, target_exe}:
                proc.terminate()
                terminated += 1
        self.audit_logger.log(
            category="automation",
            action=f"Terminated {terminated} instance(s) of {process_name}",
            permission="EXECUTE",
            decision="executed",
            status="ok",
        )
        return {"process": process_name, "terminated_count": terminated}
