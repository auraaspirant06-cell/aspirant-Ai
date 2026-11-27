"""Collaborative multi-agent orchestrator coordinating all 7 specialized Aspirant AI agents."""

from __future__ import annotations

from backend.app.agents.base import BaseAgent, SharedAgentContext
from backend.app.agents.specialists import (
    AutomationAgent,
    CodingAgent,
    ContentAgent,
    PlanningAgent,
    ProductivityAgent,
    ResearchAgent,
    SupportAgent,
)
from backend.app.ai.rag import RAGPipeline
from backend.app.ai.router import MultiModelAIRouter
from backend.app.domain.entities import (
    AgentRole,
    AgentRunEntity,
    ProductSource,
    new_id,
)
from backend.app.domain.repositories import AgentRunRepository
from backend.app.memory.memory_service import MemoryService


class AgentOrchestrator:
    """Selects and coordinates specialized agents with shared context and persistent run history."""

    ROLE_KEYWORDS: dict[AgentRole, tuple[str, ...]] = {
        AgentRole.RESEARCH: ("research", "analyze", "compare", "find", "explain", "study", "deep"),
        AgentRole.AUTOMATION: ("open", "click", "automate", "browser", "clipboard", "screenshot", "ocr", "windows", "app"),
        AgentRole.CODING: ("code", "bug", "python", "typescript", "api", "fastapi", "refactor", "test", "build"),
        AgentRole.CONTENT: ("write", "draft", "email", "summary", "post", "doc", "script"),
        AgentRole.PRODUCTIVITY: ("remind", "habit", "calendar", "schedule", "today", "task", "note"),
        AgentRole.PLANNING: ("plan", "goal", "roadmap", "milestone", "strategy", "multi-step"),
        AgentRole.SUPPORT: ("help", "error", "troubleshoot", "fix", "security", "diagnose", "support"),
    }

    def __init__(
        self,
        *,
        router: MultiModelAIRouter,
        rag: RAGPipeline,
        memory: MemoryService,
        run_repo: AgentRunRepository,
    ) -> None:
        self._memory = memory
        self._runs = run_repo
        self._agents: dict[AgentRole, BaseAgent] = {
            AgentRole.RESEARCH: ResearchAgent(router, rag),
            AgentRole.AUTOMATION: AutomationAgent(router),
            AgentRole.CODING: CodingAgent(router),
            AgentRole.CONTENT: ContentAgent(router),
            AgentRole.PRODUCTIVITY: ProductivityAgent(router),
            AgentRole.PLANNING: PlanningAgent(router),
            AgentRole.SUPPORT: SupportAgent(router),
        }

    def select_agents(self, objective: str, requested: list[AgentRole] | None = None) -> list[AgentRole]:
        if requested:
            return requested
        lowered = objective.lower()
        chosen: list[AgentRole] = [AgentRole.PLANNING]
        for role, keywords in self.ROLE_KEYWORDS.items():
            if role == AgentRole.PLANNING:
                continue
            if any(kw in lowered for kw in keywords):
                chosen.append(role)
        if len(chosen) == 1:
            chosen.extend([AgentRole.RESEARCH, AgentRole.CONTENT])
        if AgentRole.SUPPORT not in chosen:
            chosen.append(AgentRole.SUPPORT)
        return chosen

    def catalog(self) -> list[dict[str, str]]:
        return [
            {"role": role.value, "description": agent.capability_summary}
            for role, agent in self._agents.items()
        ]

    async def execute_objective(
        self,
        *,
        user_id: str,
        objective: str,
        source_app: ProductSource = ProductSource.NOVA,
        requested_agents: list[AgentRole] | None = None,
    ) -> AgentRunEntity:
        memory_bundle = await self._memory.recall_context_bundle(user_id=user_id, topic=objective)
        selected = self.select_agents(objective, requested_agents)
        ctx = SharedAgentContext(
            user_id=user_id,
            objective=objective,
            source_app=source_app.value,
            memory_bundle=memory_bundle,
        )
        steps: list[dict] = []
        for idx, role in enumerate(selected, start=1):
            agent = self._agents[role]
            msg = await agent.execute(ctx)
            steps.append(
                {
                    "order": idx,
                    "agent": role.value,
                    "output": msg.content,
                    "artifacts": msg.artifacts,
                }
            )
        final_output = "\n".join(f"[{s['agent'].upper()}] {s['output']}" for s in steps)
        run = AgentRunEntity(
            id=new_id(),
            user_id=user_id,
            objective=objective,
            source_app=source_app,
            selected_agents=[r.value for r in selected],
            plan_steps=steps,
            final_output=final_output,
            status="completed",
        )
        return await self._runs.save_run(run)
