"""Base multi-agent primitives and shared collaborative message bus."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.ai.router import MultiModelAIRouter
from backend.app.domain.entities import AgentRole


@dataclass(slots=True)
class AgentMessage:
    sender: AgentRole
    content: str
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass
class SharedAgentContext:
    """Shared collaboration state passed sequentially and across stages between specialized agents."""

    user_id: str
    objective: str
    source_app: str
    memory_bundle: dict[str, Any] = field(default_factory=dict)
    messages: list[AgentMessage] = field(default_factory=list)
    shared_facts: dict[str, Any] = field(default_factory=dict)

    def post(self, sender: AgentRole, content: str, artifacts: dict[str, Any] | None = None) -> None:
        self.messages.append(
            AgentMessage(sender=sender, content=content, artifacts=artifacts or {})
        )
        if artifacts:
            self.shared_facts[sender.value] = artifacts

    def prior_summary(self) -> str:
        if not self.messages:
            return "No prior agent messages yet."
        return "\n".join(f"- {m.sender.value}: {m.content[:240]}" for m in self.messages)


class BaseAgent:
    role: AgentRole
    capability_summary: str

    def __init__(self, router: MultiModelAIRouter) -> None:
        self._router = router

    async def execute(self, ctx: SharedAgentContext) -> AgentMessage:
        raise NotImplementedError
