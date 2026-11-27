"""OpenAI-compatible provider adapter (OpenAI, Groq, OpenRouter, LM Studio)."""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from aspirant.providers.base import (
    ChatRequest,
    ChatResponse,
    LLMProvider,
    ProviderError,
    ProviderHealth,
    StreamChunk,
)


class OpenAICompatProvider(LLMProvider):
    """Generic async OpenAI SDK adapter supporting configurable base URLs."""

    def __init__(
        self,
        provider_id: str,
        display_name: str,
        api_key: str | None,
        base_url: str,
        default_model: str,
    ) -> None:
        self.provider_id = provider_id
        self.display_name = display_name
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.mode = "cloud"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _client(self, timeout: float = 45.0) -> AsyncOpenAI:
        if not self.api_key:
            raise ProviderError(self.provider_id, "API key is not configured.")
        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout)

    def _build_messages(self, request: ChatRequest) -> list[dict[str, Any]]:
        msgs: list[dict[str, Any]] = []
        if request.system_instruction:
            msgs.append({"role": "system", "content": request.system_instruction})
        for m in request.messages:
            msgs.append({"role": m.role, "content": m.content})
        return msgs

    async def health_check(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(
                provider_id=self.provider_id,
                name=self.display_name,
                configured=False,
                healthy=False,
                detail="API key not set.",
                available_models=[self.default_model],
                mode=self.mode,
            )
        t0 = time.perf_counter()
        try:
            client = self._client(timeout=8.0)
            models = await client.models.list()
            ids = [m.id for m in models.data[:12]] if getattr(models, "data", None) else [self.default_model]
            return ProviderHealth(
                provider_id=self.provider_id,
                name=self.display_name,
                configured=True,
                healthy=True,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                detail=f"Connected ({self.base_url})",
                available_models=ids,
                mode=self.mode,
            )
        except Exception as exc:
            return ProviderHealth(
                provider_id=self.provider_id,
                name=self.display_name,
                configured=True,
                healthy=False,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                detail=str(exc)[:180],
                available_models=[self.default_model],
                mode=self.mode,
            )

    async def generate(self, request: ChatRequest) -> ChatResponse:
        client = self._client(timeout=request.timeout_seconds)
        model = request.model or self.default_model
        messages = self._build_messages(request)
        for attempt in range(3):
            t0 = time.perf_counter()
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
                latency = (time.perf_counter() - t0) * 1000.0
                text = resp.choices[0].message.content or "" if resp.choices else ""
                usage = resp.usage
                return ChatResponse(
                    text=text,
                    provider=self.provider_id,
                    model=model,
                    input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                    output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                    latency_ms=latency,
                )
            except Exception as exc:
                msg = str(exc).lower()
                retryable = any(tok in msg for tok in ("429", "503", "timeout", "rate"))
                if attempt < 2 and retryable:
                    await asyncio.sleep(0.8 * (2**attempt))
                    continue
                raise ProviderError(self.provider_id, str(exc), retryable=retryable) from exc
        raise ProviderError(self.provider_id, "Exhausted retries.")

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        client = self._client(timeout=request.timeout_seconds)
        model = request.model or self.default_model
        messages = self._build_messages(request)
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield StreamChunk(
                        delta_text=chunk.choices[0].delta.content,
                        done=False,
                        provider=self.provider_id,
                        model=model,
                    )
            yield StreamChunk(delta_text="", done=True, provider=self.provider_id, model=model)
        except Exception as exc:
            raise ProviderError(self.provider_id, str(exc)) from exc
