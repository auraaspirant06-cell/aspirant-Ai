"""MAX mobile companion service: voice commands, daily planner, habits, reminders, notes, push, and sync."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.app.ai.router import MultiModelAIRouter
from backend.app.domain.entities import ProductSource
from backend.app.memory.memory_service import MemoryService
from backend.app.services.productivity_service import ProductivityService
from backend.app.workers.tasks import dispatch_push_notification_task


class MAXService:
    """Serves Android-first mobile workflows, offline delta reconciliation, and push notifications."""

    def __init__(
        self,
        *,
        router: MultiModelAIRouter,
        memory: MemoryService,
        productivity: ProductivityService,
    ) -> None:
        self._router = router
        self._memory = memory
        self._productivity = productivity

    async def mobile_chat(self, *, user_id: str, message: str, channel: str = "chat") -> dict[str, Any]:
        await self._memory.record_conversation_turn(
            user_id=user_id,
            role="user",
            message=message,
            source_app=ProductSource.MAX,
        )
        res = await self._router.generate(
            prompt=message,
            system_instruction="Respond like MAX mobile companion: concise, clear, mobile-glanceable.",
            task_type="fast",
        )
        await self._memory.record_conversation_turn(
            user_id=user_id,
            role="assistant",
            message=res.text,
            source_app=ProductSource.MAX,
        )
        return {
            "reply": res.text,
            "channel": channel,
            "provider": res.provider,
            "model": res.model,
        }

    async def build_daily_plan(self, *, user_id: str) -> dict[str, Any]:
        snap = await self._productivity.snapshot_for_sync(user_id)
        pending_reminders = [r for r in snap["reminders"] if not r.completed]
        active_goals = [g for g in snap["goals"] if g.status == "active"]
        return {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "focus_goals": [{"id": g.id, "title": g.title, "progress": g.progress} for g in active_goals[:3]],
            "due_reminders": [{"id": r.id, "title": r.title, "due_at": r.due_at} for r in pending_reminders[:5]],
            "habits": [{"id": h.id, "title": h.title, "streak": h.streak} for h in snap["habits"]],
            "recent_notes_count": len(snap["notes"]),
        }

    def trigger_device_integration(self, *, capability: str, payload: dict[str, Any]) -> dict[str, Any]:
        supported = {"dnd", "alarm", "calendar_intent", "notification_channel", "battery_saver"}
        return {
            "capability": capability,
            "supported": capability in supported,
            "android_intent_payload": {"action": f"ai.aspirant.max.{capability.upper()}", **payload},
        }

    def enqueue_push(self, *, user_id: str, title: str, body: str) -> dict[str, Any]:
        result = dispatch_push_notification_task.delay(user_id, title, body, "max-android")
        return result.get(timeout=5) if hasattr(result, "get") else {"status": "queued", "title": title}

    async def sync_mobile_delta(
        self,
        *,
        user_id: str,
        offline_notes: list[dict[str, Any]],
        habit_checkins: list[str],
    ) -> dict[str, Any]:
        for note in offline_notes:
            await self._productivity.save_note(
                user_id=user_id,
                note_id=note.get("id"),
                title=str(note.get("title", "Mobile Note")),
                content=str(note.get("content", "")),
                tags=list(note.get("tags", ["mobile-offline"])),
                source_app=ProductSource.MAX,
            )
        existing_habits = {h.id: h for h in await self._productivity.list_habits(user_id)}
        for hid in habit_checkins:
            habit = existing_habits.get(hid)
            if habit:
                await self._productivity.create_or_checkin_habit(
                    user_id=user_id,
                    habit_id=habit.id,
                    title=habit.title,
                    cadence=habit.cadence,
                    mark_done_today=True,
                )
        snap = await self._productivity.snapshot_for_sync(user_id)
        return {
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "notes": [
                {"id": n.id, "title": n.title, "content": n.content, "ai_summary": n.ai_summary}
                for n in snap["notes"]
            ],
            "habits": [
                {"id": h.id, "title": h.title, "streak": h.streak, "last_completed_on": h.last_completed_on}
                for h in snap["habits"]
            ],
            "reminders": [
                {"id": r.id, "title": r.title, "due_at": r.due_at, "completed": r.completed}
                for r in snap["reminders"]
            ],
            "goals": [
                {"id": g.id, "title": g.title, "progress": g.progress, "status": g.status}
                for g in snap["goals"]
            ],
        }
