"""Unified goals, habits, reminders, AI notes, and cross-device delta sync endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import AuthenticatedPrincipal, get_container, get_current_user, get_db_session
from backend.app.core.container import EcosystemContainer
from backend.app.domain.entities import ProductSource


router = APIRouter(prefix="/productivity", tags=["Productivity & Sync"])


class GoalRequest(BaseModel):
    goal_id: str | None = None
    title: str = Field(min_length=1)
    description: str = ""
    progress: int = Field(default=0, ge=0, le=100)
    status: str = "active"
    target_date: str | None = None
    milestones: list[dict] = Field(default_factory=list)


class HabitRequest(BaseModel):
    habit_id: str | None = None
    title: str = Field(min_length=1)
    cadence: str = "daily"
    mark_done_today: bool = False


class ReminderRequest(BaseModel):
    reminder_id: str | None = None
    title: str = Field(min_length=1)
    due_at: str
    channel: str = "push"
    completed: bool = False
    context_note: str = ""


class NoteRequest(BaseModel):
    note_id: str | None = None
    title: str
    content: str
    ai_summary: str = ""
    tags: list[str] = Field(default_factory=list)
    source_app: ProductSource = ProductSource.MAX


@router.get("/sync")
async def sync_snapshot(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    svc = container.build_productivity_service(session)
    snap = await svc.snapshot_for_sync(principal.user.id)
    return {
        "goals": [
            {
                "id": g.id,
                "title": g.title,
                "description": g.description,
                "progress": g.progress,
                "status": g.status,
                "target_date": g.target_date,
                "milestones": g.milestones,
            }
            for g in snap["goals"]
        ],
        "habits": [
            {
                "id": h.id,
                "title": h.title,
                "cadence": h.cadence,
                "streak": h.streak,
                "last_completed_on": h.last_completed_on,
            }
            for h in snap["habits"]
        ],
        "reminders": [
            {
                "id": r.id,
                "title": r.title,
                "due_at": r.due_at,
                "channel": r.channel,
                "completed": r.completed,
                "context_note": r.context_note,
            }
            for r in snap["reminders"]
        ],
        "notes": [
            {
                "id": n.id,
                "title": n.title,
                "content": n.content,
                "ai_summary": n.ai_summary,
                "tags": n.tags,
                "source_app": n.source_app.value,
            }
            for n in snap["notes"]
        ],
    }


@router.post("/goals")
async def save_goal(
    body: GoalRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    svc = container.build_productivity_service(session)
    g = await svc.create_or_update_goal(user_id=principal.user.id, **body.model_dump())
    return {"id": g.id, "title": g.title, "progress": g.progress, "status": g.status}


@router.post("/habits")
async def save_habit(
    body: HabitRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    svc = container.build_productivity_service(session)
    h = await svc.create_or_checkin_habit(user_id=principal.user.id, **body.model_dump())
    return {"id": h.id, "title": h.title, "streak": h.streak, "last_completed_on": h.last_completed_on}


@router.post("/reminders")
async def save_reminder(
    body: ReminderRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    svc = container.build_productivity_service(session)
    r = await svc.create_or_update_reminder(user_id=principal.user.id, **body.model_dump())
    return {"id": r.id, "title": r.title, "due_at": r.due_at, "completed": r.completed}


@router.post("/notes")
async def save_note(
    body: NoteRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    svc = container.build_productivity_service(session)
    n = await svc.save_note(user_id=principal.user.id, **body.model_dump())
    return {"id": n.id, "title": n.title, "ai_summary": n.ai_summary, "tags": n.tags}
