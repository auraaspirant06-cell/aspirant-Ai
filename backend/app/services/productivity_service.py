"""Unified productivity service powering MJ planning and MAX mobile sync."""

from __future__ import annotations

from datetime import date

from backend.app.domain.entities import (
    GoalEntity,
    HabitEntity,
    NoteEntity,
    ProductSource,
    ReminderEntity,
    new_id,
)
from backend.app.domain.repositories import ProductivityRepository


class ProductivityService:
    """Manages goals, habits, reminders, AI notes, and cross-device sync payloads."""

    def __init__(self, repo: ProductivityRepository) -> None:
        self._repo = repo

    async def create_or_update_goal(
        self,
        *,
        user_id: str,
        title: str,
        description: str = "",
        progress: int = 0,
        status: str = "active",
        target_date: str | None = None,
        milestones: list[dict] | None = None,
        goal_id: str | None = None,
    ) -> GoalEntity:
        goal = GoalEntity(
            id=goal_id or new_id(),
            user_id=user_id,
            title=title.strip(),
            description=description,
            status=status,
            progress=max(0, min(100, progress)),
            target_date=target_date,
            milestones=milestones or [],
        )
        return await self._repo.upsert_goal(goal)

    async def list_goals(self, user_id: str) -> list[GoalEntity]:
        return await self._repo.list_goals(user_id)

    async def create_or_checkin_habit(
        self,
        *,
        user_id: str,
        title: str,
        cadence: str = "daily",
        habit_id: str | None = None,
        mark_done_today: bool = False,
    ) -> HabitEntity:
        existing = None
        if habit_id:
            for h in await self._repo.list_habits(user_id):
                if h.id == habit_id:
                    existing = h
                    break
        today_iso = date.today().isoformat()
        streak = existing.streak if existing else 0
        last_done = existing.last_completed_on if existing else None
        if mark_done_today and last_done != today_iso:
            streak += 1
            last_done = today_iso
        habit = HabitEntity(
            id=habit_id or new_id(),
            user_id=user_id,
            title=title.strip(),
            cadence=cadence,
            streak=streak,
            last_completed_on=last_done,
        )
        return await self._repo.upsert_habit(habit)

    async def list_habits(self, user_id: str) -> list[HabitEntity]:
        return await self._repo.list_habits(user_id)

    async def create_or_update_reminder(
        self,
        *,
        user_id: str,
        title: str,
        due_at: str,
        channel: str = "push",
        completed: bool = False,
        context_note: str = "",
        reminder_id: str | None = None,
    ) -> ReminderEntity:
        reminder = ReminderEntity(
            id=reminder_id or new_id(),
            user_id=user_id,
            title=title.strip(),
            due_at=due_at,
            channel=channel,
            completed=completed,
            context_note=context_note,
        )
        return await self._repo.upsert_reminder(reminder)

    async def list_reminders(self, user_id: str) -> list[ReminderEntity]:
        return await self._repo.list_reminders(user_id)

    async def save_note(
        self,
        *,
        user_id: str,
        title: str,
        content: str,
        ai_summary: str = "",
        tags: list[str] | None = None,
        source_app: ProductSource = ProductSource.MAX,
        note_id: str | None = None,
    ) -> NoteEntity:
        if not ai_summary.strip() and content.strip():
            sentences = [s.strip() for s in content.replace("\n", ". ").split(".") if s.strip()]
            ai_summary = ". ".join(sentences[:2])[:280]
        note = NoteEntity(
            id=note_id or new_id(),
            user_id=user_id,
            title=title.strip() or "Untitled Note",
            content=content,
            ai_summary=ai_summary,
            tags=tags or [],
            source_app=source_app,
        )
        return await self._repo.upsert_note(note)

    async def list_notes(self, user_id: str) -> list[NoteEntity]:
        return await self._repo.list_notes(user_id)

    async def snapshot_for_sync(self, user_id: str) -> dict:
        return {
            "goals": await self.list_goals(user_id),
            "habits": await self.list_habits(user_id),
            "reminders": await self.list_reminders(user_id),
            "notes": await self.list_notes(user_id),
        }
