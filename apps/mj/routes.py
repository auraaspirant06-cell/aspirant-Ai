"""FastAPI routes for MJ Human-Like Intelligent Assistant."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.mj.service import MJService
from backend.app.api.deps import AuthenticatedPrincipal, get_container, get_current_user, get_db_session
from backend.app.core.container import EcosystemContainer


router = APIRouter(prefix="/mj", tags=["MJ Intelligence"])


class MJChatRequest(BaseModel):
    message: str = Field(min_length=1)
    mode: str = "companion"


class DocumentUnderstandRequest(BaseModel):
    title: str
    content: str = Field(min_length=1)


class EmailAssistRequest(BaseModel):
    recipient: str
    subject: str
    context: str
    tone: str = "professional-warm"


class CalendarAnalyzeRequest(BaseModel):
    events: list[dict[str, str]] = Field(default_factory=list)


class DeepResearchPlanRequest(BaseModel):
    topic: str = Field(min_length=2)
    create_goal: bool = True


def _service(container: EcosystemContainer, session: AsyncSession) -> MJService:
    return MJService(
        router=container.ai_router,
        rag=container.rag,
        memory=container.build_memory_service(session),
        productivity=container.build_productivity_service(session),
        orchestrator=container.build_orchestrator(session),
    )


@router.post("/chat")
async def mj_chat(
    body: MJChatRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _service(container, session).converse(
        user_id=principal.user.id, message=body.message, mode=body.mode
    )


@router.post("/document/understand")
async def understand_document(
    body: DocumentUnderstandRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _service(container, session).understand_document(
        user_id=principal.user.id, title=body.title, content=body.content
    )


@router.post("/email/assist")
async def assist_email(
    body: EmailAssistRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _service(container, session).assist_email(
        user_id=principal.user.id,
        recipient=body.recipient,
        subject=body.subject,
        context=body.context,
        tone=body.tone,
    )


@router.post("/calendar/analyze")
async def analyze_calendar(
    body: CalendarAnalyzeRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return _service(container, session).analyze_calendar(body.events)


@router.post("/research/plan")
async def deep_research_and_plan(
    body: DeepResearchPlanRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _service(container, session).deep_research_and_plan(
        user_id=principal.user.id, topic=body.topic, create_goal=body.create_goal
    )
