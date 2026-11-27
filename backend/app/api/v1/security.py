"""Security posture and audit log inspection endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import AuthenticatedPrincipal, get_container, get_current_user, get_db_session
from backend.app.core.container import EcosystemContainer


router = APIRouter(prefix="/security", tags=["Security & Audit"])


@router.get("/posture")
async def security_posture(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    audit = container.build_audit_service(session)
    return {
        "user_id": principal.user.id,
        "posture": audit.security_posture(),
        "vector_backend": container.vector_store.active_backend,
        "cache_mode": container.cache.mode,
    }


@router.get("/audit-logs")
async def list_audit_logs(
    limit: int = 50,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    audit = container.build_audit_service(session)
    events = await audit.list_recent(user_id=principal.user.id, limit=min(200, max(1, limit)))
    return {
        "events": [
            {
                "id": e.id,
                "action": e.action,
                "resource": e.resource,
                "outcome": e.outcome,
                "ip_address": e.ip_address,
                "details": e.details,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]
    }
