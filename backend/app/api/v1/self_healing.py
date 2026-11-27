"""Self-healing diagnostics, crash recovery journal & auto-repair API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import AuthenticatedPrincipal, get_current_user
from backend.app.self_healing.healer import CrashRecoveryJournal, RepositorySelfHealer


router = APIRouter(prefix="/self-healing", tags=["Self-Healing System"])


def _api_paths(request: Request) -> set[str]:
    return set(request.app.openapi().get("paths", {}).keys())


@router.get("/audit")
async def run_audit(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    return RepositorySelfHealer().run_audit(repair=False, app_routes_paths=_api_paths(request)).to_dict()


@router.post("/repair")
async def run_repair(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    return RepositorySelfHealer().run_audit(repair=True, app_routes_paths=_api_paths(request)).to_dict()


@router.get("/crashes")
async def list_crashes(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    return {"crashes": CrashRecoveryJournal().list_crashes()}


@router.post("/recover")
async def recover_platform(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    return CrashRecoveryJournal().recover()
