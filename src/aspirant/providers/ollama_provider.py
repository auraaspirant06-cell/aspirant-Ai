"""Local Ollama LLM adapter with low-RAM guardrails for 8 GB Windows hosts."""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

import httpx
import psutil

from aspirant.providers.base import (
    ChatRequest,
    ChatResponse,
    LLMProvider,
    ProviderError,
    ProviderHealth,
    StreamChunk,
)


class OllamaProvider(LLMProvider):
    """Connects to a local Ollama server at http://127.0.0.1:11434."""

    provider_id = "ollama"
    display_name = "Ollama (Local)"
    default_model = "qwen2.5:1.5b"
    mode = "local"

    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def _build_messages(self, request: ChatRequest) -> list[dict[str, Any]]:
        msgs: list[dict[str, Any]] = []
        if request.system_instruction:
            msgs.append({"role": "system", "content": request.system_instruction})
        for m in request.messages:
            msgs.append({"role": m.role, "content": m.content})
        return msgs

    async def health_check(self) -> ProviderHealth:
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=3.0) as client:
                resp = await client.get("/api/tags")
                resp.raise_for_status()
                models = [m.get("name", "") for m in resp.json().get("models", []) if m.get("name")]
            avail_mb = round(psutil.virtual_memory().available / (1024 * 1024))
            ram_note = " (Low free RAM: prefer 1B-1.5B models)" if avail_mb < 1600 else ""
            return ProviderHealth(
                provider_id=self.provider_id,
                name=self.display_name,
                configured=True,
                healthy=True,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                detail=f"Ollama running ({len(models)} local models){ram_note}",
                available_models=models or [self.default_model],
                mode=self.mode,
            )
        except Exception:
            return ProviderHealth(
                provider_id=self.provider_id,
                name=self.display_name,
                configured=True,
                healthy=False,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                detail="Ollama service not running on local host.",
                available_models=[self.default_model],
                mode=self.mode,
            )

    async def generate(self, request: ChatRequest) -> ChatResponse:
        model = request.model or self.default_model
        payload = {
            "model": model,
            "messages": self._build_messages(request),
            "stream": False,
            "options": {"temperature": request.temperature, "num_predict": request.max_tokens},
        }
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=request.timeout_seconds) as client:
                resp = await client.post("/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
            text = data.get("message", {}).get("content", "")
            return ChatResponse(
                text=text,
                provider=self.provider_id,
                model=model,
                input_tokens=int(data.get("prompt_eval_count", 0) or 0),
                output_tokens=int(data.get("eval_count", 0) or 0),
                latency_ms=(time.perf_counter() - t0) * 1000.0,
            )
        except Exception as exc:
            raise ProviderError(self.provider_id, f"Ollama request failed: {exc}") from exc

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        model = request.model or self.default_model
        payload = {
            "model": model,
            "messages": self._build_messages(request),
            "stream": True,
            "options": {"temperature": request.temperature, "num_predict": request.max_tokens},
        }
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=request.timeout_seconds) as client:
                async with client.stream("POST", "/api/chat", json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        obj = json.loads(line)
                        delta = obj.get("message", {}).get("content", "")
                        done = bool(obj.get("done", False))
                        yield StreamChunk(
                            delta_text=delta,
                            done=done,
                            provider=self.provider_id,
                            model=model,
                            input_tokens=int(obj.get("prompt_eval_count", 0) or 0) if done else 0,
                            output_tokens=int(obj.get("eval_count", 0) or 0) if done else 0,
                        )
        except Exception as exc:
            raise ProviderError(self.provider_id, f"Ollama stream failed: {exc}") from exc
