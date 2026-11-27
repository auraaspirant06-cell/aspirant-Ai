"""Abstract interfaces and normalized request/response models for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


class ProviderError(RuntimeError):
    """Raised when an AI provider fails or is misconfigured."""

    def __init__(self, provider_id: str, message: str, retryable: bool = False) -> None:
        self.provider_id = provider_id
        self.retryable = retryable
        super().__init__(f"[{provider_id}] {message}")


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass(frozen=True, slots=True)
class ChatRequest:
    messages: list[ChatMessage]
    system_instruction: str = ""
    model: str | None = None
    temperature: float = 0.4
    max_tokens: int = 1024
    timeout_seconds: float = 45.0


@dataclass(frozen=True, slots=True)
class ChatResponse:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    interaction_id: str | None = None


@dataclass(frozen=True, slots=True)
class StreamChunk:
    delta_text: str
    done: bool = False
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    interaction_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    provider_id: str
    name: str
    configured: bool
    healthy: bool
    latency_ms: float = 0.0
    detail: str = ""
    available_models: list[str] = field(default_factory=list)
    mode: str = "cloud"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.provider_id,
            "name": self.name,
            "configured": self.configured,
            "healthy": self.healthy,
            "latency_ms": round(self.latency_ms, 1),
            "detail": self.detail,
            "available_models": self.available_models,
            "mode": self.mode,
        }


class LLMProvider(ABC):
    """Base contract for hot-swappable text/multimodal LLM backends."""

    provider_id: str
    display_name: str
    default_model: str
    mode: str = "cloud"

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if required credentials or local URL are configured."""

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Verify provider reachability without burning generation quota."""

    @abstractmethod
    async def generate(self, request: ChatRequest) -> ChatResponse:
        """Generate a complete response with timeouts and retries."""

    @abstractmethod
    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        """Stream incremental text chunks from the provider."""
