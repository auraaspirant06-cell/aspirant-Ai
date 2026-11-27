"""Modular FastAPI router for Smart Memory CRUD, encrypted backup/restore, and local auth."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aspirant.security.auth import check_windows_hello_available
from aspirant.security.backup import create_encrypted_backup, restore_encrypted_backup
from aspirant.security.permissions import Permission, PermissionDeniedError


class PreferenceSetRequest(BaseModel):
    key: str
    value: Any
    category: str = "general"


class BackupCreateRequest(BaseModel):
    passphrase: str


class BackupRestoreRequest(BaseModel):
    backup_path: str
    passphrase: str


class PinSetRequest(BaseModel):
    pin: str


def create_memory_router(container: Any, auth_dependency: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1/memory", dependencies=[auth_dependency])

    @router.get("/search")
    async def search_memory(q: str) -> dict[str, Any]:
        try:
            container.permissions.require(Permission.READ, f"Search local memory '{q[:40]}'", category="memory")
            return {"items": container.memory.search_messages(q, limit=40)}
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.get("/preferences")
    async def list_preferences() -> dict[str, Any]:
        return {"items": container.memory.list_preferences()}

    @router.post("/preferences")
    async def set_preference(body: PreferenceSetRequest) -> dict[str, Any]:
        try:
            container.permissions.require(Permission.WRITE, f"Save preference {body.key}", category="memory")
            return container.memory.set_preference(body.key, body.value, category=body.category)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.delete("/preferences/{key}")
    async def delete_preference(key: str) -> dict[str, Any]:
        try:
            container.permissions.require(Permission.WRITE, f"Delete preference {key}", category="memory")
            return {"deleted": container.memory.delete_preference(key), "key": key}
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.post("/backup")
    async def backup_data(body: BackupCreateRequest) -> dict[str, Any]:
        try:
            container.permissions.require(Permission.WRITE, "Create encrypted Aspirant backup", category="security")
            res = create_encrypted_backup(container.settings.resolved_data_dir, body.passphrase)
            container.audit_logger.log(
                category="security",
                action=f"Created encrypted backup ({len(res['files'])} files)",
                permission="WRITE",
                decision="executed",
                status="ok",
            )
            return res
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/restore")
    async def restore_data(body: BackupRestoreRequest) -> dict[str, Any]:
        try:
            container.permissions.require(Permission.WRITE, "Restore encrypted Aspirant backup", category="security")
            return restore_encrypted_backup(
                Path(body.backup_path).expanduser().resolve(),
                body.passphrase,
                container.settings.resolved_data_dir,
            )
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/auth/status")
    async def auth_status() -> dict[str, Any]:
        return {
            **container.local_auth.status(),
            "windows_hello": check_windows_hello_available(),
        }

    @router.post("/auth/pin")
    async def set_pin(body: PinSetRequest) -> dict[str, Any]:
        try:
            container.local_auth.set_pin(body.pin)
            container.audit_logger.log(
                category="security",
                action="Configured local PIN lock",
                permission="WRITE",
                decision="updated",
                status="ok",
            )
            return container.local_auth.status()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/auth/lock")
    async def lock_session() -> dict[str, Any]:
        container.local_auth.lock()
        return container.local_auth.status()

    @router.post("/auth/unlock")
    async def unlock_session(body: PinSetRequest) -> dict[str, Any]:
        ok = container.local_auth.unlock(body.pin)
        if not ok:
            raise HTTPException(status_code=401, detail="Invalid PIN.")
        return container.local_auth.status()

    return router
