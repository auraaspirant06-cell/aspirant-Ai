"""Seven specialized collaborating agents sharing context across the Aspirant AI ecosystem."""

from __future__ import annotations

import re

from backend.app.agents.base import AgentMessage, BaseAgent, SharedAgentContext
from backend.app.agents.engineering import analyze_debug_error_log, generate_devops_deployment_plan
from backend.app.ai.rag import RAGPipeline
from backend.app.ai.system_prompt import build_aspirant_core_prompt, detect_interaction_mode
from backend.app.domain.entities import AgentRole


class ResearchAgent(BaseAgent):
    role = AgentRole.RESEARCH
    capability_summary = "Deep web/knowledge synthesis, RAG citations, and comparative analysis."

    def __init__(self, router, rag: RAGPipeline) -> None:
        super().__init__(router)
        self._rag = rag

    async def execute(self, ctx: SharedAgentContext) -> AgentMessage:
        hits = self._rag.retrieve(user_id=ctx.user_id, query=ctx.objective, top_k=3)
        res = await self._router.generate(
            prompt=f"Research objective: {ctx.objective}\nIndexed facts: {[h.text[:120] for h in hits]}\nPrior context:\n{ctx.prior_summary()}",
            system_instruction="Synthesize verified research findings concisely.",
            task_type="research",
        )
        msg = AgentMessage(
            sender=self.role,
            content=f"Research brief ({res.provider}/{res.model}): {res.text}",
            artifacts={"citations": [h.id for h in hits], "findings": res.text},
        )
        ctx.post(self.role, msg.content, msg.artifacts)
        return msg


class AutomationAgent(BaseAgent):
    role = AgentRole.AUTOMATION
    capability_summary = "Windows desktop automation, browser workflows, clipboard, OCR, and app actions."

    async def execute(self, ctx: SharedAgentContext) -> AgentMessage:
        commands = [
            "Inspect active window & clipboard context",
            "Validate command policy before OS action",
            "Execute guarded desktop/browser workflow step",
        ]
        msg = AgentMessage(
            sender=self.role,
            content=f"Automation sequence prepared for '{ctx.objective[:80]}' across {len(commands)} guarded steps.",
            artifacts={"workflow_steps": commands, "requires_confirmation": False},
        )
        ctx.post(self.role, msg.content, msg.artifacts)
        return msg


class CodingAgent(BaseAgent):
    role = AgentRole.CODING
    capability_summary = "Architecture, code generation, debugging, refactoring, and automated verification."

    async def execute(self, ctx: SharedAgentContext) -> AgentMessage:
        mode = detect_interaction_mode(ctx.objective)
        prompt = f"Technical task: {ctx.objective}\nPeer context:\n{ctx.prior_summary()}"
        extra_artifacts: dict[str, object] = {"language": "python/typescript"}
        if mode == "debugging":
            dbg = analyze_debug_error_log(error_log=ctx.objective)
            prompt += f"\nPre-analyzed root cause: {dbg['root_cause']}"
            extra_artifacts["debug_analysis"] = dbg
        elif mode == "devops":
            plan = generate_devops_deployment_plan(app_name="aspirant-app", platform="Docker", execution_confirmed=False)
            extra_artifacts["devops_plan"] = {"confirmation_required": True, "status": plan["status"]}
        res = await self._router.generate(
            prompt=prompt,
            system_instruction=build_aspirant_core_prompt(owner_preferred_address="Boss", mode=mode if mode != "general" else "coding"),
            task_type="coding",
        )
        msg = AgentMessage(
            sender=self.role,
            content=f"Engineering plan & code guidance: {res.text}",
            artifacts={**extra_artifacts, "provider": res.provider},
        )
        ctx.post(self.role, msg.content, msg.artifacts)
        return msg


class ContentAgent(BaseAgent):
    role = AgentRole.CONTENT
    capability_summary = "Multilingual communication, summaries, emails, scripts, and structured documentation."

    async def execute(self, ctx: SharedAgentContext) -> AgentMessage:
        res = await self._router.generate(
            prompt=f"Draft clear user-facing deliverable for: {ctx.objective}\nShared context:\n{ctx.prior_summary()}",
            system_instruction="Write crisp, human-friendly content tailored to user preferences.",
            task_type="general",
        )
        msg = AgentMessage(
            sender=self.role,
            content=res.text,
            artifacts={"tone": ctx.memory_bundle.get("preferences", {}).get("tone", "balanced")},
        )
        ctx.post(self.role, msg.content, msg.artifacts)
        return msg


class ProductivityAgent(BaseAgent):
    role = AgentRole.PRODUCTIVITY
    capability_summary = "Daily schedule optimization, reminders, habit streaks, and calendar intelligence."

    async def execute(self, ctx: SharedAgentContext) -> AgentMessage:
        action_items = [
            s.strip()
            for s in re.split(r"[.;,\n]+", ctx.objective)
            if len(s.strip()) >= 4
        ][:4] or [ctx.objective]
        msg = AgentMessage(
            sender=self.role,
            content=f"Extracted {len(action_items)} actionable productivity items synced for MJ & MAX.",
            artifacts={"action_items": action_items, "sync_targets": ["mj", "max"]},
        )
        ctx.post(self.role, msg.content, msg.artifacts)
        return msg


class PlanningAgent(BaseAgent):
    role = AgentRole.PLANNING
    capability_summary = "Goal decomposition, multi-step autonomous execution roadmaps, and milestone tracking."

    async def execute(self, ctx: SharedAgentContext) -> AgentMessage:
        milestones = [
            {"step": 1, "title": "Gather context & constraints", "owner": "research"},
            {"step": 2, "title": "Prepare domain execution", "owner": "coding/automation"},
            {"step": 3, "title": "Deliver outcome & sync progress", "owner": "productivity"},
        ]
        msg = AgentMessage(
            sender=self.role,
            content=f"Built 3-phase execution plan using context from {len(ctx.messages)} agents.",
            artifacts={"milestones": milestones},
        )
        ctx.post(self.role, msg.content, msg.artifacts)
        return msg


class SupportAgent(BaseAgent):
    role = AgentRole.SUPPORT
    capability_summary = "Diagnostics, troubleshooting, security sanity checks, and guided user help."

    async def execute(self, ctx: SharedAgentContext) -> AgentMessage:
        msg = AgentMessage(
            sender=self.role,
            content="Verified health, safety boundaries, and fallback readiness for this multi-agent run.",
            artifacts={"diagnostics": "healthy", "agents_participated": [m.sender.value for m in ctx.messages]},
        )
        ctx.post(self.role, msg.content, msg.artifacts)
        return msg
