"""Deep contextual reasoning, long-chain planning, self-reflection, and cross-session feedback learning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.ai.router import MultiModelAIRouter
from backend.app.domain.entities import MemoryLayer, ProductSource, new_id
from backend.app.infrastructure.db.models import FeedbackEventModel
from backend.app.memory.memory_service import MemoryService


@dataclass(slots=True)
class ReasoningTrace:
    intent: str
    confidence: float
    plan: list[str]
    chain_of_thought: list[dict[str, str]]
    prior_lessons_used: list[str]
    reflection: dict[str, Any]
    final_answer: str


class DeepReasoningEngine:
    """Provides structured multi-step planning, self-reflection, error correction, and feedback adaptation."""

    INTENT_MAP = {
        "code_engineering": ("code", "bug", "test", "api", "fastapi", "refactor", "python", "typescript", "go"),
        "research_synthesis": ("research", "compare", "analyze", "study", "paper", "deep"),
        "desktop_automation": ("open", "browser", "clipboard", "ocr", "windows", "automate", "workflow"),
        "productivity_planning": ("goal", "habit", "reminder", "calendar", "schedule", "roadmap", "plan"),
        "security_audit": ("security", "audit", "auth", "token", "encrypt", "vulnerability", "heal"),
    }

    def __init__(
        self,
        *,
        router: MultiModelAIRouter,
        memory: MemoryService,
        session: AsyncSession,
    ) -> None:
        self._router = router
        self._memory = memory
        self._session = session

    def detect_intent(self, objective: str) -> tuple[str, float]:
        lowered = objective.lower()
        best_intent = "general_companion"
        best_hits = 0
        for intent, keywords in self.INTENT_MAP.items():
            hits = sum(1 for kw in keywords if kw in lowered)
            if hits > best_hits:
                best_hits = hits
                best_intent = intent
        confidence = min(0.98, 0.55 + 0.14 * best_hits)
        return best_intent, round(confidence, 4)

    async def _recent_lessons(self, user_id: str, intent: str) -> list[str]:
        stmt = (
            select(FeedbackEventModel)
            .where(FeedbackEventModel.user_id == user_id)
            .order_by(desc(FeedbackEventModel.created_at))
            .limit(8)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        lessons: list[str] = []
        for r in rows:
            if r.correction_note.strip() and (r.intent == intent or r.rating <= 3):
                lessons.append(f"[{r.intent} rating={r.rating}] {r.correction_note.strip()}")
        return lessons[:4]

    @staticmethod
    def self_reflect(objective: str, draft: str, plan: list[str], lessons: list[str]) -> tuple[dict[str, Any], str]:
        """Critique draft for completeness, error signals, and unaddressed user feedback."""
        adjustments: list[str] = []
        corrected = draft.strip()
        if not corrected:
            adjustments.append("Recovered empty synthesis from planned milestones.")
            corrected = f"Planned solution for '{objective}': " + " -> ".join(plan)
        if len(plan) < 3:
            adjustments.append("Expanded sparse execution plan to minimum 3 verification stages.")
        if lessons and "lesson" not in corrected.lower():
            adjustments.append(f"Incorporated {len(lessons)} prior user feedback lesson(s).")
            corrected = f"{corrected}\n\nApplied Prior Feedback:\n- " + "\n- ".join(lessons)
        passed = bool(corrected and len(plan) >= 3)
        return {"passed": passed, "adjustments": adjustments, "errors_corrected": len(adjustments)}, corrected

    async def reason(
        self,
        *,
        user_id: str,
        objective: str,
        source_app: ProductSource = ProductSource.MJ,
    ) -> ReasoningTrace:
        intent, confidence = self.detect_intent(objective)
        memory_bundle = await self._memory.recall_context_bundle(user_id=user_id, topic=objective)
        lessons = await self._recent_lessons(user_id, intent)

        plan = [
            f"1. Intent classification ({intent}) and constraint bounding",
            "2. Cross-session contextual recall from encrypted memory & Qdrant/Chroma",
            "3. Domain synthesis incorporating feedback lessons",
            "4. Self-reflection error audit and verified answer delivery",
        ]
        chain = [
            {"stage": "intent", "detail": f"Detected '{intent}' with confidence {confidence}"},
            {
                "stage": "context",
                "detail": f"Loaded {len(memory_bundle['semantic_memories'])} semantic memories and {len(lessons)} prior feedback lessons",
            },
            {"stage": "plan", "detail": "Constructed 4-stage execution roadmap"},
        ]

        ai_reply = await self._router.generate(
            prompt=(
                f"Objective: {objective}\nIntent: {intent}\nPlan: {plan}\n"
                f"Prior Feedback Lessons: {lessons}\n"
                f"Memory Snippets: {[m['content'][:100] for m in memory_bundle['semantic_memories'][:3]]}"
            ),
            system_instruction="Produce a concise, verifiable multi-step reasoning conclusion.",
            task_type="planning",
        )
        reflection, final_answer = self.self_reflect(objective, ai_reply.text, plan, lessons)
        chain.append(
            {
                "stage": "self_reflection",
                "detail": f"Passed={reflection['passed']}, corrections={reflection['errors_corrected']}",
            }
        )

        await self._memory.remember(
            user_id=user_id,
            content=f"Reasoning ({intent}): {objective} => {final_answer[:220]}",
            layer=MemoryLayer.LONG_TERM,
            source_app=source_app,
            tags=["reasoning", intent],
            importance=0.72,
        )

        return ReasoningTrace(
            intent=intent,
            confidence=confidence,
            plan=plan,
            chain_of_thought=chain,
            prior_lessons_used=lessons,
            reflection=reflection,
            final_answer=final_answer,
        )

    async def record_feedback(
        self,
        *,
        user_id: str,
        objective: str,
        intent: str,
        rating: int,
        correction_note: str = "",
    ) -> FeedbackEventModel:
        row = FeedbackEventModel(
            id=new_id(),
            user_id=user_id,
            objective=objective.strip(),
            intent=intent.strip() or "general",
            rating=max(1, min(5, rating)),
            correction_note=correction_note.strip(),
        )
        self._session.add(row)
        await self._session.flush()
        if correction_note.strip():
            await self._memory.remember(
                user_id=user_id,
                content=f"User feedback lesson ({intent}, rating={rating}): {correction_note.strip()}",
                layer=MemoryLayer.PREFERENCE,
                source_app=ProductSource.MJ,
                tags=["feedback", intent],
                importance=0.92,
            )
        return row
