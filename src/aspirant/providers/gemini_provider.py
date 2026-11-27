"""Google Gemini provider adapter using the official google-genai Interactions API."""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

from google import genai

from aspirant.providers.base import (
    ChatRequest,
    ChatResponse,
    LLMProvider,
    ProviderError,
    ProviderHealth,
    StreamChunk,
)


GEMINI_MODELS = [
    "gemini-4-hydrogen",
    "gemini-4-argon",
    "gemini-4-carbon",
    "gemini-4-neon",
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
]


def _format_turns(request: ChatRequest) -> list[dict[str, Any]] | str:
    if len(request.messages) == 1 and request.messages[0].role == "user":
        return request.messages[0].content
    turns: list[dict[str, Any]] = []
    for msg in request.messages:
        role = "model" if msg.role == "assistant" else "user"
        turns.append({"role": role, "content": [{"type": "text", "text": msg.content}]})
    return turns


class GeminiLLMProvider(LLMProvider):
    """Calls Gemini 4 / 3.5 models via google-genai Interactions API."""

    provider_id = "gemini"
    display_name = "Google Gemini"
    default_model = "gemini-4-hydrogen"
    mode = "cloud"

    def __init__(self, api_key: str | None) -> None:
        self.api_key = (api_key or "").strip()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _client(self) -> genai.Client:
        if not self.api_key:
            raise ProviderError(self.provider_id, "GEMINI_API_KEY is not configured.")
        return genai.Client(api_key=self.api_key)

    async def health_check(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(
                provider_id=self.provider_id,
                name=self.display_name,
                configured=False,
                healthy=False,
                detail="GEMINI_API_KEY not set.",
                available_models=list(GEMINI_MODELS),
                mode=self.mode,
            )
        t0 = time.perf_counter()
        try:
            client = self._client()
            await asyncio.wait_for(client.aio.models.get(model=self.default_model), timeout=8.0)
            elapsed = (time.perf_counter() - t0) * 1000.0
            return ProviderHealth(
                provider_id=self.provider_id,
                name=self.display_name,
                configured=True,
                healthy=True,
                latency_ms=elapsed,
                detail="Connected to Gemini API",
                available_models=list(GEMINI_MODELS),
                mode=self.mode,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return ProviderHealth(
                provider_id=self.provider_id,
                name=self.display_name,
                configured=True,
                healthy=False,
                latency_ms=elapsed,
                detail=str(exc)[:180],
                available_models=list(GEMINI_MODELS),
                mode=self.mode,
            )

    async def generate(self, request: ChatRequest) -> ChatResponse:
        client = self._client()
        model = request.model or self.default_model
        turns = _format_turns(request)
        gen_cfg = {
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
        }

        last_exc: Exception | None = None
        for attempt in range(3):
            t0 = time.perf_counter()
            try:
                interaction = await asyncio.wait_for(
                    client.aio.interactions.create(
                        model=model,
                        input=turns,
                        system_instruction=request.system_instruction or None,
                        generation_config=gen_cfg,
                        store=False,
                    ),
                    timeout=request.timeout_seconds,
                )
                latency = (time.perf_counter() - t0) * 1000.0
                usage = getattr(interaction, "usage", None)
                in_tok = int(getattr(usage, "total_input_tokens", 0) or 0)
                out_tok = int(getattr(usage, "total_output_tokens", 0) or 0)
                text = getattr(interaction, "output_text", None) or ""
                return ChatResponse(
                    text=text,
                    provider=self.provider_id,
                    model=model,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    latency_ms=latency,
                    interaction_id=getattr(interaction, "id", None),
                )
            except Exception as exc:
                last_exc = exc
                msg = str(exc).lower()
                retryable = any(code in msg for code in ("429", "503", "timeout", "temporarily"))
                if attempt < 2 and retryable:
                    await asyncio.sleep(0.8 * (2**attempt))
                    continue
                raise ProviderError(self.provider_id, str(exc), retryable=retryable) from exc
        raise ProviderError(self.provider_id, str(last_exc))

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        client = self._client()
        model = request.model or self.default_model
        turns = _format_turns(request)
        gen_cfg = {
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
        }
        try:
            async_stream = await asyncio.wait_for(
                client.aio.interactions.create(
                    model=model,
                    input=turns,
                    system_instruction=request.system_instruction or None,
                    generation_config=gen_cfg,
                    store=False,
                    stream=True,
                ),
                timeout=request.timeout_seconds,
            )
            async for event in async_stream:
                etype = getattr(event, "event_type", "")
                if etype == "step.delta":
                    delta = getattr(event, "delta", None)
                    if getattr(delta, "type", "") == "text":
                        yield StreamChunk(
                            delta_text=getattr(delta, "text", "") or "",
                            done=False,
                            provider=self.provider_id,
                            model=model,
                        )
                elif etype == "interaction.completed":
                    inter = getattr(event, "interaction", None)
                    usage = getattr(inter, "usage", None)
                    yield StreamChunk(
                        delta_text="",
                        done=True,
                        provider=self.provider_id,
                        model=model,
                        input_tokens=int(getattr(usage, "total_input_tokens", 0) or 0),
                        output_tokens=int(getattr(usage, "total_output_tokens", 0) or 0),
                        interaction_id=getattr(inter, "id", None),
                    )
        except Exception as exc:
            raise ProviderError(self.provider_id, str(exc)) from exc
