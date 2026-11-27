"""Windows 11 Operating Layer: window enumeration/focus/minimize, safe app launch, file search & org, notifications."""

from __future__ import annotations

import ctypes
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
ALLOWED_WINDOWS_APPS = {
    "notepad": "notepad.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
    "mspaint": "mspaint.exe",
    "code": "code",
}
PROTECTED_FRAGMENTS = ("windows", "system32", ".ssh", "appdata\\local\\google", "vault.enc")


def list_desktop_windows(limit: int = 25) -> dict[str, Any]:
    """Enumerate visible top-level windows cleanly on Windows, with container fallback elsewhere."""
    if platform.system().lower() != "windows":
        return {"platform": platform.system(), "windows": [], "note": "Desktop window enumeration active on Windows hosts."}

    user32 = ctypes.windll.user32
    windows: list[dict[str, Any]] = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def _cb(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()
                if title:
                    windows.append({"hwnd": int(hwnd), "title": title})
        return len(windows) < limit

    user32.EnumWindows(EnumWindowsProc(_cb), 0)
    return {"platform": "Windows", "windows": windows}


def manage_window(
    *, action: str, title_query: str, authorized: bool = False
) -> dict[str, Any]:
    """Focus, minimize, maximize, or close (authorization-gated) a matching window."""
    act = action.lower().strip()
    if act == "close" and not authorized:
        return {
            "action": act,
            "title_query": title_query,
            "executed": False,
            "requires_authorization": True,
            "detail": "Closing an active application window requires explicit user authorization.",
        }

    if platform.system().lower() != "windows":
        return {"action": act, "title_query": title_query, "executed": False, "detail": "Windows-only operation"}

    win_list = list_desktop_windows(50)["windows"]
    match = next((w for w in win_list if title_query.lower() in w["title"].lower()), None)
    if not match:
        return {"action": act, "title_query": title_query, "executed": False, "detail": "No matching window found."}

    user32 = ctypes.windll.user32
    hwnd = match["hwnd"]
    sw_map = {"minimize": 6, "maximize": 3, "focus": 9, "restore": 9}
    if act in sw_map:
        user32.ShowWindow(hwnd, sw_map[act])
        if act == "focus":
            user32.SetForegroundWindow(hwnd)
        return {"action": act, "window": match, "executed": True}
    if act == "close":
        user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        return {"action": act, "window": match, "executed": True}
    return {"action": act, "window": match, "executed": False, "detail": f"Unsupported action: {act}"}


def _is_safe_path(target: Path) -> bool:
    lowered = str(target.resolve()).lower()
    return not any(frag in lowered for frag in PROTECTED_FRAGMENTS)


def search_workspace_files(*, query: str, directory: str | None = None, limit: int = 25) -> dict[str, Any]:
    base = Path(directory) if directory else ROOT_DIR
    if not base.exists() or not _is_safe_path(base):
        raise PermissionError("Search directory unavailable or protected by NOVA safety boundary.")
    needle = query.lower().strip()
    matches: list[str] = []
    skip_dirs = {".venv", "node_modules", ".next", ".git", "__pycache__"}
    for p in base.rglob("*"):
        if any(part in skip_dirs for part in p.parts):
            continue
        if p.is_file() and needle in p.name.lower():
            matches.append(str(p))
            if len(matches) >= limit:
                break
    return {"directory": str(base), "query": query, "matches": matches}


def organize_directory(
    *, directory: str, dry_run: bool = True, authorized: bool = False
) -> dict[str, Any]:
    target = Path(directory)
    if not target.exists() or not _is_safe_path(target):
        raise PermissionError("Organization target directory does not exist or is protected.")
    if not dry_run and not authorized:
        return {
            "directory": str(target),
            "dry_run": dry_run,
            "requires_authorization": True,
            "detail": "Applying file moves requires explicit authorization (`authorized=True`).",
        }

    categories = {
        "Images": {".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"},
        "Documents": {".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx"},
        "Archives": {".zip", ".tar", ".gz", ".7z"},
        "Code": {".py", ".ts", ".tsx", ".js", ".go", ".rs", ".json"},
    }
    planned: list[dict[str, str]] = []
    for item in target.iterdir():
        if not item.is_file():
            continue
        ext = item.suffix.lower()
        dest_folder = next((cat for cat, exts in categories.items() if ext in exts), "Other")
        dest_dir = target / dest_folder
        planned.append({"file": item.name, "destination_folder": dest_folder})
        if not dry_run:
            dest_dir.mkdir(exist_ok=True)
            shutil.move(str(item), str(dest_dir / item.name))
    return {"directory": str(target), "dry_run": dry_run, "planned_moves": planned, "applied": not dry_run}


def send_windows_notification(*, title: str, message: str) -> dict[str, Any]:
    return {
        "platform": platform.system(),
        "title": title,
        "message": message,
        "delivered_channel": "windows-toast-bridge",
        "ready": True,
    }


def launch_safe_application(*, app_name: str, authorized: bool = False) -> dict[str, Any]:
    key = app_name.lower().strip()
    exe = ALLOWED_WINDOWS_APPS.get(key)
    if not exe:
        return {
            "app_name": app_name,
            "launched": False,
            "requires_authorization": True,
            "detail": f"App '{app_name}' is not in the fast allowlist; explicit confirmation required.",
        }
    if platform.system().lower() == "windows" and authorized:
        subprocess.Popen([exe])
        return {"app_name": app_name, "executable": exe, "launched": True}
    return {"app_name": app_name, "executable": exe, "launched": False, "ready_to_launch": True}
