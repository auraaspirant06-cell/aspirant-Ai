"""Official Social Platform connector API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import AuthenticatedPrincipal, get_container, get_current_user, get_db_session
from backend.app.core.container import EcosystemContainer
from backend.app.integrations.social import SocialIntegrationManager


router = APIRouter(prefix="/integrations", tags=["Social Integrations"])


class ConnectSocialRequest(BaseModel):
    platform: str
    access_token: str = Field(min_length=4)
    permissions: list[str] = Field(default_factory=lambda: ["read"])
    metadata: dict[str, Any] = Field(default_factory=dict)


class DispatchSocialRequest(BaseModel):
    platform: str
    permission: str = "publish"
    payload: dict[str, Any] = Field(default_factory=dict)
    live_send: bool = False


class WebhookEventRequest(BaseModel):
    platform: str
    event: dict[str, Any]


@router.get("/catalog")
async def catalog(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    mgr = SocialIntegrationManager(session=session, crypto=container.crypto)
    return {"connectors": await mgr.catalog(principal.user.id)}


@router.post("/connect")
async def connect_platform(
    body: ConnectSocialRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    mgr = SocialIntegrationManager(session=session, crypto=container.crypto)
    audit = container.build_audit_service(session)
    try:
        conn = await mgr.connect(
            user_id=principal.user.id,
            platform=body.platform,
            access_token=body.access_token,
            permissions=body.permissions,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await audit.record(
        user_id=principal.user.id,
        action="integrations.connect",
        resource=conn.platform,
        outcome="success",
        details={"permissions": list(conn.permissions_json)},
    )
    return {"platform": conn.platform, "connected": conn.is_enabled, "permissions": conn.permissions_json}


@router.delete("/{platform}")
async def disconnect_platform(
    platform: str,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    mgr = SocialIntegrationManager(session=session, crypto=container.crypto)
    try:
        removed = await mgr.disconnect(user_id=principal.user.id, platform=platform)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"platform": platform, "disconnected": removed}


@router.post("/dispatch")
async def dispatch_social(
    body: DispatchSocialRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    mgr = SocialIntegrationManager(session=session, crypto=container.crypto)
    try:
        return await mgr.dispatch_action(
            user_id=principal.user.id,
            platform=body.platform,
            required_permission=body.permission,
            payload=body.payload,
            live_send=body.live_send,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/event")
async def process_webhook_event(
    body: WebhookEventRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    mgr = SocialIntegrationManager(session=session, crypto=container.crypto)
    try:
        return mgr.normalize_webhook_event(platform=body.platform, raw_event=body.event)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
