"""FastAPI routes for MAX Mobile AI Companion."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.max.service import MAXService
from backend.app.api.deps import AuthenticatedPrincipal, get_container, get_current_user, get_db_session
from backend.app.core.container import EcosystemContainer


router = APIRouter(prefix="/max", tags=["MAX Mobile Companion"])


class MobileChatRequest(BaseModel):
    message: str = Field(min_length=1)
    channel: str = "chat"


class PushRequest(BaseModel):
    title: str
    body: str


class DeviceIntegrationRequest(BaseModel):
    capability: str
    payload: dict[str, Any] = Field(default_factory=dict)


class MobileSyncRequest(BaseModel):
    offline_notes: list[dict[str, Any]] = Field(default_factory=list)
    habit_checkins: list[str] = Field(default_factory=list)


def _service(container: EcosystemContainer, session: AsyncSession) -> MAXService:
    return MAXService(
        router=container.ai_router,
        memory=container.build_memory_service(session),
        productivity=container.build_productivity_service(session),
    )


@router.post("/chat")
async def max_chat(
    body: MobileChatRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _service(container, session).mobile_chat(
        user_id=principal.user.id, message=body.message, channel=body.channel
    )


@router.post("/voice-command")
async def max_voice_command(
    body: MobileChatRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _service(container, session).mobile_chat(
        user_id=principal.user.id, message=body.message, channel="voice"
    )


@router.get("/daily-plan")
async def daily_plan(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _service(container, session).build_daily_plan(user_id=principal.user.id)


@router.post("/push")
async def push_notification(
    body: PushRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return _service(container, session).enqueue_push(
        user_id=principal.user.id, title=body.title, body=body.body
    )


@router.post("/device-integration")
async def device_integration(
    body: DeviceIntegrationRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return _service(container, session).trigger_device_integration(
        capability=body.capability, payload=body.payload
    )


@router.post("/sync")
async def mobile_sync(
    body: MobileSyncRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _service(container, session).sync_mobile_delta(
        user_id=principal.user.id,
        offline_notes=body.offline_notes,
        habit_checkins=body.habit_checkins,
    )
