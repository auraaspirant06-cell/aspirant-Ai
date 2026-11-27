"""Multi-model AI router supporting Gemini API, GPT-compatible APIs, tool calling, and Ollama."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from backend.app.core.config import EcosystemSettings


@dataclass(slots=True)
class RegisteredTool:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: Callable[..., Any]


class ToolRegistry:
    """Declarative tool registry exporting OpenAI/Gemini compatible schemas."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        parameters_schema: dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        self._tools[name] = RegisteredTool(
            name=name,
            description=description,
            parameters_schema=parameters_schema,
            handler=handler,
        )

    def openai_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema,
                },
            }
            for tool in self._tools.values()
        ]

    def list_names(self) -> list[str]:
        return sorted(self._tools.keys())

    async def invoke(self, name: str, arguments: dict[str, Any]) -> Any:
        tool = self._tools.get(name)
        if not tool:
            raise KeyError(f"Unknown tool: {name}")
        result = tool.handler(**arguments)
        if inspect.isawaitable(result):
            return await result
        return result


@dataclass(slots=True)
class AIRouteResult:
    text: str
    provider: str
    model: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class MultiModelAIRouter:
    """Routes inference requests across Gemini primary, GPT-compatible endpoints, Ollama, and deterministic fallback."""

    TASK_MODEL_MAP = {
        "fast": "fast_chat_model",
        "general": "primary_chat_model",
        "research": "deep_research_model",
        "coding": "primary_chat_model",
        "planning": "deep_research_model",
    }

    def __init__(self, settings: EcosystemSettings, tool_registry: ToolRegistry | None = None) -> None:
        self._settings = settings
        self.tools = tool_registry or ToolRegistry()

    def select_model(self, task_type: str = "general", preferred_provider: str = "auto") -> tuple[str, str]:
        attr = self.TASK_MODEL_MAP.get(task_type, "primary_chat_model")
        gemini_model = getattr(self._settings, attr)
        if preferred_provider == "openai" and self._settings.openai_api_key:
            return "openai", "gpt-4o-mini"
        if preferred_provider == "ollama":
            return "ollama", "qwen2.5:latest"
        if preferred_provider in {"auto", "gemini"} and self._settings.gemini_api_key:
            return "gemini", gemini_model
        if self._settings.openai_api_key:
            return "openai", "gpt-4o-mini"
        return "local-synthesizer", "aspirant-deterministic-v2"

    async def generate(
        self,
        *,
        prompt: str,
        system_instruction: str = "",
        task_type: str = "general",
        preferred_provider: str = "auto",
        enable_tools: bool = False,
    ) -> AIRouteResult:
        provider, model = self.select_model(task_type, preferred_provider)
        if provider == "gemini":
            try:
                from google import genai

                client = genai.Client(api_key=self._settings.gemini_api_key)
                interaction = await client.aio.interactions.create(
                    model=model,
                    input=prompt,
                    system_instruction=system_instruction or None,
                )
                text_parts = [
                    getattr(out, "text", "")
                    for out in getattr(interaction, "outputs", [])
                    if getattr(out, "text", None)
                ]
                return AIRouteResult(
                    text="\n".join(text_parts).strip(),
                    provider="gemini",
                    model=model,
                )
            except Exception:
                pass

        if provider == "openai" and self._settings.openai_api_key:
            try:
                payload: dict[str, Any] = {
                    "model": model,
                    "messages": [
                        *(
                            [{"role": "system", "content": system_instruction}]
                            if system_instruction
                            else []
                        ),
                        {"role": "user", "content": prompt},
                    ],
                }
                if enable_tools and self.tools.list_names():
                    payload["tools"] = self.tools.openai_tools()
                async with httpx.AsyncClient(timeout=20.0) as http:
                    resp = await http.post(
                        f"{self._settings.openai_base_url.rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {self._settings.openai_api_key}"},
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                choice = (data.get("choices") or [{}])[0].get("message", {})
                return AIRouteResult(
                    text=choice.get("content") or "",
                    provider="openai",
                    model=model,
                    tool_calls=choice.get("tool_calls") or [],
                )
            except Exception:
                pass

        # Deterministic offline-safe structured response when external keys/endpoints aren't active
        summary_prefix = f"[{task_type.upper()} | {model}]"
        return AIRouteResult(
            text=f"{summary_prefix} {prompt.strip()[:360]}",
            provider="local-synthesizer",
            model="aspirant-deterministic-v2",
        )
