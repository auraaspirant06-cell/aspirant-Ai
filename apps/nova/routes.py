"""FastAPI routes for NOVA Desktop AI Assistant."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.nova.service import NovaService
from apps.nova.windows_integration import (
    launch_safe_application,
    list_desktop_windows,
    manage_window,
    organize_directory,
    search_workspace_files,
    send_windows_notification,
)
from backend.app.api.deps import AuthenticatedPrincipal, get_container, get_current_user, get_db_session
from backend.app.core.container import EcosystemContainer


router = APIRouter(prefix="/nova", tags=["NOVA Desktop AI"])


class WakeWordRequest(BaseModel):
    transcript: str


class ClipboardRequest(BaseModel):
    content: str


class OCRImageRequest(BaseModel):
    image_base64: str


class CommandEvaluateRequest(BaseModel):
    command: str = Field(min_length=1)


class VoiceCommandRequest(BaseModel):
    transcript: str = Field(min_length=1)


class WorkflowRequest(BaseModel):
    name: str = Field(min_length=1)
    steps: list[dict[str, Any]] = Field(default_factory=list)


def _service(container: EcosystemContainer, session: AsyncSession) -> NovaService:
    return NovaService(
        router=container.ai_router,
        memory=container.build_memory_service(session),
        orchestrator=container.build_orchestrator(session),
    )


@router.post("/wake-word")
async def detect_wake_word(
    body: WakeWordRequest,
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return _service(container, session).detect_wake_word(body.transcript)


@router.post("/clipboard/analyze")
async def analyze_clipboard(
    body: ClipboardRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return _service(container, session).analyze_clipboard(body.content)


@router.post("/screen/ocr")
async def screen_ocr(
    body: OCRImageRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        return _service(container, session).analyze_screenshot_or_ocr(body.image_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image payload: {exc}") from exc


@router.post("/command/evaluate")
async def evaluate_command(
    body: CommandEvaluateRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return _service(container, session).evaluate_command(body.command)


@router.post("/voice/command")
async def voice_command(
    body: VoiceCommandRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _service(container, session).process_voice_command(
        user_id=principal.user.id,
        transcript=body.transcript,
    )


@router.post("/workflow/run")
async def run_workflow(
    body: WorkflowRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _service(container, session).run_workflow(
        user_id=principal.user.id,
        name=body.name,
        steps=body.steps,
    )


class WindowManageRequest(BaseModel):
    action: str
    title_query: str
    authorized: bool = False


class SearchFilesRequest(BaseModel):
    query: str = Field(min_length=1)
    directory: str | None = None


class OrganizeDirRequest(BaseModel):
    directory: str
    dry_run: bool = True
    authorized: bool = False


class LaunchAppRequest(BaseModel):
    app_name: str
    authorized: bool = False


class NotifyRequest(BaseModel):
    title: str
    message: str


@router.get("/windows/list")
async def windows_list(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    return list_desktop_windows()


@router.post("/windows/manage")
async def windows_manage(
    body: WindowManageRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    return manage_window(
        action=body.action, title_query=body.title_query, authorized=body.authorized
    )


@router.post("/windows/search-files")
async def windows_search_files(
    body: SearchFilesRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    try:
        return search_workspace_files(query=body.query, directory=body.directory)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/windows/organize")
async def windows_organize(
    body: OrganizeDirRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    try:
        return organize_directory(
            directory=body.directory, dry_run=body.dry_run, authorized=body.authorized
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/windows/launch")
async def windows_launch_app(
    body: LaunchAppRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    return launch_safe_application(app_name=body.app_name, authorized=body.authorized)


@router.post("/windows/notify")
async def windows_notify(
    body: NotifyRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    return send_windows_notification(title=body.title, message=body.message)
