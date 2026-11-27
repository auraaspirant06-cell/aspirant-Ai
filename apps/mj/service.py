"""MJ intelligent companion service: persistent memory, profiling, deep research, email/calendar, planning."""

from __future__ import annotations

from typing import Any

from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.ai.rag import RAGPipeline
from backend.app.ai.router import MultiModelAIRouter
from backend.app.ai.system_prompt import build_aspirant_core_prompt, detect_interaction_mode
from backend.app.domain.entities import AgentRole, MemoryLayer, ProductSource
from backend.app.memory.memory_service import MemoryService
from backend.app.services.productivity_service import ProductivityService
from backend.app.workers.tasks import deep_research_task


class MJService:
    """Human-like deep reasoning and personal intelligence engine."""

    def __init__(
        self,
        *,
        router: MultiModelAIRouter,
        rag: RAGPipeline,
        memory: MemoryService,
        productivity: ProductivityService,
        orchestrator: AgentOrchestrator,
    ) -> None:
        self._router = router
        self._rag = rag
        self._memory = memory
        self._productivity = productivity
        self._orchestrator = orchestrator

    async def converse(self, *, user_id: str, message: str, mode: str = "companion") -> dict[str, Any]:
        bundle = await self._memory.recall_context_bundle(user_id=user_id, topic=message)
        await self._memory.record_conversation_turn(
            user_id=user_id,
            role="user",
            message=message,
            source_app=ProductSource.MJ,
        )
        recall_snippets = [m["content"][:140] for m in bundle["semantic_memories"][:3]]
        sys_prompt = build_aspirant_core_prompt(
            owner_preferred_address="Boss",
            mode=detect_interaction_mode(message),
        )
        res = await self._router.generate(
            prompt=(
                f"User profile: {bundle['user_profile']}\n"
                f"Preferences: {bundle['preferences']}\n"
                f"Recalled context: {recall_snippets}\n"
                f"User message ({mode}): {message}"
            ),
            system_instruction=sys_prompt,
            task_type="general" if mode == "companion" else "research",
        )
        await self._memory.record_conversation_turn(
            user_id=user_id,
            role="assistant",
            message=res.text,
            source_app=ProductSource.MJ,
        )
        return {
            "reply": res.text,
            "provider": res.provider,
            "model": res.model,
            "recalled_count": len(bundle["semantic_memories"]),
            "preferences_applied": bundle["preferences"],
        }

    async def understand_document(
        self, *, user_id: str, title: str, content: str
    ) -> dict[str, Any]:
        ingest = self._rag.ingest_document(
            user_id=user_id, title=title, content=content, source="mj-document"
        )
        await self._memory.remember(
            user_id=user_id,
            content=f"Document '{title}': {content[:500]}",
            layer=MemoryLayer.KNOWLEDGE,
            source_app=ProductSource.MJ,
            summary=f"Indexed document '{title}' ({ingest.chunk_count} chunks)",
            tags=["document", title.lower().replace(" ", "-")],
        )
        res = await self._router.generate(
            prompt=f"Summarize key takeaways and action items from '{title}':\n\n{content[:3000]}",
            system_instruction="Produce structured executive takeaways and concrete action items.",
            task_type="research",
        )
        return {
            "document_id": ingest.document_id,
            "chunks_indexed": ingest.chunk_count,
            "vector_backend": ingest.backend,
            "summary": res.text,
        }

    async def assist_email(
        self, *, user_id: str, recipient: str, subject: str, context: str, tone: str = "professional-warm"
    ) -> dict[str, Any]:
        bundle = await self._memory.recall_context_bundle(user_id=user_id, topic=f"{recipient} {subject}")
        res = await self._router.generate(
            prompt=(
                f"Draft an email to {recipient} about '{subject}'. Tone: {tone}.\n"
                f"Context: {context}\nKnown preferences: {bundle['preferences']}"
            ),
            system_instruction="Draft a clear, natural email ready to send.",
            task_type="general",
        )
        return {"subject": subject, "recipient": recipient, "tone": tone, "draft": res.text}

    def analyze_calendar(self, events: list[dict[str, str]]) -> dict[str, Any]:
        sorted_events = sorted(events, key=lambda e: e.get("start", ""))
        overlaps: list[dict[str, Any]] = []
        for idx in range(len(sorted_events) - 1):
            curr = sorted_events[idx]
            nxt = sorted_events[idx + 1]
            if curr.get("end", "") > nxt.get("start", ""):
                overlaps.append({"first": curr.get("title"), "second": nxt.get("title")})
        return {
            "event_count": len(sorted_events),
            "conflicts": overlaps,
            "focus_recommendation": (
                "Schedule 90m deep work block before noon; resolve overlapping meetings."
                if overlaps
                else "Calendar conflict-free; reserve first open 90m block for high-priority goal."
            ),
        }

    async def deep_research_and_plan(
        self, *, user_id: str, topic: str, create_goal: bool = True
    ) -> dict[str, Any]:
        deep_research_task.delay(user_id, topic, "deep")
        run = await self._orchestrator.execute_objective(
            user_id=user_id,
            objective=f"Deep research and multi-step execution plan for: {topic}",
            source_app=ProductSource.MJ,
            requested_agents=[AgentRole.RESEARCH, AgentRole.PLANNING, AgentRole.CONTENT, AgentRole.PRODUCTIVITY],
        )
        goal_id = None
        if create_goal:
            goal = await self._productivity.create_or_update_goal(
                user_id=user_id,
                title=topic[:180],
                description="Created automatically by MJ Planning Engine",
                milestones=[{"step": s["order"], "title": s["agent"]} for s in run.plan_steps],
            )
            goal_id = goal.id
        return {
            "run_id": run.id,
            "goal_id": goal_id,
            "agents": run.selected_agents,
            "plan_steps": run.plan_steps,
            "synthesis": run.final_output,
        }
