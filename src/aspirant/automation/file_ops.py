"""Sandboxed file operations with protected path checks and trash-safe rollback."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any

from aspirant.security.audit import AuditLogger
from aspirant.security.command_policy import is_protected_path
from aspirant.security.permissions import Permission, PermissionManager

_CATEGORY_EXTENSIONS: dict[str, set[str]] = {
    "Documents": {".pdf", ".docx", ".doc", ".txt", ".md", ".xlsx", ".csv", ".pptx"},
    "Images": {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"},
    "Videos": {".mp4", ".mkv", ".mov", ".avi", ".webm"},
    "Audio": {".mp3", ".wav", ".ogg", ".flac", ".m4a"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml"},
}


def _classify_extension(suffix: str) -> str:
    ext = suffix.lower()
    for folder, exts in _CATEGORY_EXTENSIONS.items():
        if ext in exts:
            return folder
    return "Other"


class FileManagerEngine:
    """Safe, permission-checked file browsing, search, organization, and trash-safe edits."""

    def __init__(
        self,
        data_dir: Path,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
    ) -> None:
        self.trash_dir = (data_dir / "trash").resolve()
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        self.permissions = permissions
        self.audit_logger = audit_logger

    def _guard_path(self, path: str | Path) -> Path:
        p = Path(path).expanduser().resolve()
        blocked, reason = is_protected_path(p)
        if blocked:
            raise PermissionError(reason)
        return p

    def list_directory(self, path: str) -> dict[str, Any]:
        self.permissions.require(Permission.READ, f"List directory {path}", category="files")
        target = self._guard_path(path)
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"Directory not found: {target}")

        entries: list[dict[str, Any]] = []
        for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:300]:
            try:
                stat = item.stat()
                entries.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "is_dir": item.is_dir(),
                        "size_bytes": 0 if item.is_dir() else stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    }
                )
            except OSError:
                continue
        return {"path": str(target), "entries": entries}

    def search_files(self, root_path: str, pattern: str, max_results: int = 80) -> list[dict[str, Any]]:
        self.permissions.require(Permission.READ, f"Search '{pattern}' in {root_path}", category="files")
        root = self._guard_path(root_path)
        if not root.is_dir():
            raise FileNotFoundError(f"Directory not found: {root}")
        matches: list[dict[str, Any]] = []
        needle = pattern.strip().lower()
        for item in root.rglob("*"):
            if len(matches) >= max_results:
                break
            blocked, _ = is_protected_path(item)
            if blocked:
                continue
            if needle in item.name.lower():
                matches.append({"name": item.name, "path": str(item), "is_dir": item.is_dir()})
        return matches

    def read_text(self, path: str, max_chars: int = 40_000) -> dict[str, Any]:
        self.permissions.require(Permission.READ, f"Read file {path}", category="files")
        target = self._guard_path(path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {target}")
        raw = target.read_text(encoding="utf-8", errors="replace")
        truncated = len(raw) > max_chars
        return {"path": str(target), "content": raw[:max_chars], "truncated": truncated}

    def write_text(self, path: str, content: str, overwrite: bool = False) -> dict[str, Any]:
        self.permissions.require(Permission.WRITE, f"Write file {path}", category="files")
        target = self._guard_path(path)
        if target.exists() and not overwrite:
            raise FileExistsError(f"File already exists and overwrite=False: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.audit_logger.log(
            category="files",
            action=f"Wrote {target.name}",
            permission="WRITE",
            decision="executed",
            status="ok",
            details={"path": str(target), "bytes": len(content.encode("utf-8"))},
        )
        return {"path": str(target), "written": True}

    def rename_or_move(self, src: str, dst: str) -> dict[str, Any]:
        self.permissions.require(Permission.WRITE, f"Move/rename {src} -> {dst}", category="files")
        src_p = self._guard_path(src)
        dst_p = self._guard_path(dst)
        if not src_p.exists():
            raise FileNotFoundError(f"Source does not exist: {src_p}")
        if dst_p.exists():
            raise FileExistsError(f"Destination already exists: {dst_p}")
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_p), str(dst_p))
        self.audit_logger.log(
            category="files",
            action=f"Moved {src_p.name} -> {dst_p}",
            permission="WRITE",
            decision="executed",
            status="ok",
        )
        return {"src": str(src_p), "dst": str(dst_p), "moved": True}

    def trash_delete(self, path: str) -> dict[str, Any]:
        """Move file/folder to reversible local trash instead of irreversible permanent delete."""
        self.permissions.require(Permission.WRITE, f"Move to trash: {path}", category="files")
        target = self._guard_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Path not found: {target}")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest = self.trash_dir / f"{stamp}_{target.name}"
        shutil.move(str(target), str(dest))
        self.audit_logger.log(
            category="files",
            action=f"Moved {target.name} to reversible trash",
            permission="WRITE",
            decision="executed",
            status="ok",
            details={"original": str(target), "trash_path": str(dest)},
        )
        return {"deleted": True, "reversible": True, "trash_path": str(dest)}

    def organize_folder(self, directory: str, dry_run: bool = True) -> dict[str, Any]:
        """Group loose files inside a folder by category (preview first with dry_run=True)."""
        perm = Permission.READ if dry_run else Permission.WRITE
        self.permissions.require(perm, f"Organize folder {directory} (dry_run={dry_run})", category="files")
        root = self._guard_path(directory)
        if not root.is_dir():
            raise FileNotFoundError(f"Directory not found: {root}")

        plan: list[dict[str, str]] = []
        for item in root.iterdir():
            if not item.is_file():
                continue
            category = _classify_extension(item.suffix)
            dest = root / category / item.name
            if dest.exists():
                continue
            plan.append({"src": str(item), "dst": str(dest), "category": category})
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(item), str(dest))

        return {"directory": str(root), "dry_run": dry_run, "planned_moves": plan, "count": len(plan)}
