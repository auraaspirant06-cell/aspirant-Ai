"""Hot-swappable multi-provider registry backed by AppSettings and SecretVault."""

from __future__ import annotations

from typing import AsyncIterator

from aspirant.core.config import AppSettings
from aspirant.providers.base import (
    ChatRequest,
    ChatResponse,
    LLMProvider,
    ProviderError,
    ProviderHealth,
    StreamChunk,
)
from aspirant.providers.gemini_provider import GeminiLLMProvider
from aspirant.providers.ollama_provider import OllamaProvider
from aspirant.providers.openai_compat import OpenAICompatProvider
from aspirant.providers.usage import UsageTracker
from aspirant.security.vault import SecretVault


class ProviderRegistry:
    """Manages active LLM providers, encrypted credential overrides, and fallback."""

    def __init__(
        self,
        settings: AppSettings,
        vault: SecretVault,
        usage_tracker: UsageTracker,
    ) -> None:
        self.settings = settings
        self.vault = vault
        self.usage_tracker = usage_tracker
        self.active_provider_id: str = "auto"
        self.active_model: str | None = None
        self._providers: dict[str, LLMProvider] = {}
        self.reload()

    def _effective_secret(self, vault_key: str, env_value: str | None) -> str | None:
        return self.vault.get_secret(vault_key) or env_value

    def reload(self) -> None:
        """Rebuild provider instances from current environment + encrypted vault keys."""
        gemini_key = self._effective_secret("GEMINI_API_KEY", self.settings.gemini_api_key)
        openai_key = self._effective_secret("OPENAI_API_KEY", self.settings.openai_api_key)
        openai_url = self._effective_secret("OPENAI_BASE_URL", self.settings.openai_base_url) or self.settings.openai_base_url
        groq_key = self._effective_secret("GROQ_API_KEY", self.settings.groq_api_key)
        ollama_url = self._effective_secret("OLLAMA_BASE_URL", self.settings.ollama_base_url) or self.settings.ollama_base_url

        self._providers = {
            "gemini": GeminiLLMProvider(api_key=gemini_key),
            "openai": OpenAICompatProvider(
                provider_id="openai",
                display_name="OpenAI-Compatible",
                api_key=openai_key,
                base_url=openai_url,
                default_model="gpt-4o-mini",
            ),
            "groq": OpenAICompatProvider(
                provider_id="groq",
                display_name="Groq (OpenAI-Compatible)",
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
                default_model="llama-3.3-70b-versatile",
            ),
            "ollama": OllamaProvider(base_url=ollama_url),
        }

    def configure_secret(self, key_name: str, value: str) -> None:
        """Store an encrypted credential in SecretVault and reload providers."""
        allowed = {
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "GROQ_API_KEY",
            "OLLAMA_BASE_URL",
            "ELEVENLABS_API_KEY",
        }
        if key_name not in allowed:
            raise ValueError(f"Unsupported provider configuration key: {key_name}")
        self.vault.set_secret(key_name, value.strip())
        self.reload()

    def get(self, provider_id: str) -> LLMProvider | None:
        return self._providers.get(provider_id)

    def register(self, provider: LLMProvider) -> None:
        """Allow registering custom or mock providers cleanly."""
        self._providers[provider.provider_id] = provider

    def select_provider(self, preferred_id: str = "auto", allow_cloud: bool = True) -> LLMProvider:
        """Pick the requested provider or the best configured fallback."""
        if preferred_id != "auto":
            prov = self._providers.get(preferred_id)
            if prov is None:
                raise ProviderError("registry", f"Unknown provider: {preferred_id}")
            if prov.mode == "cloud" and not allow_cloud:
                raise ProviderError(prov.provider_id, "NETWORK permission is disabled; only local providers allowed.")
            if not prov.is_configured():
                raise ProviderError(prov.provider_id, f"{prov.display_name} requires an API key in Connected AI Models.")
            return prov

        order = ("gemini", "openai", "groq", "ollama") if allow_cloud else ("ollama",)
        for pid in order:
            prov = self._providers.get(pid)
            if prov and prov.is_configured():
                if pid == "ollama" and not allow_cloud:
                    return prov
                if pid != "ollama":
                    return prov
        # Fall back to ollama if no cloud keys are configured
        if "ollama" in self._providers:
            return self._providers["ollama"]
        raise ProviderError("registry", "No AI provider configured.")

    def status_summary(self) -> list[dict[str, object]]:
        """Non-sensitive configuration summary for dashboard and models view."""
        items: list[dict[str, object]] = []
        for prov in self._providers.values():
            items.append(
                {
                    "id": prov.provider_id,
                    "name": prov.display_name,
                    "role": f"Default model: {prov.default_model}",
                    "configured": prov.is_configured(),
                    "mode": prov.mode,
                }
            )
        items.append(
            {
                "id": "edge_tts",
                "name": "Female Neural TTS",
                "role": f"{self.settings.voice_female_en} / {self.settings.voice_female_hi}",
                "configured": True,
                "mode": "hybrid",
            }
        )
        return items

    async def health_check_all(self) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for prov in self._providers.values():
            health: ProviderHealth = await prov.health_check()
            results.append(health.to_dict())
        return results

    async def generate(
        self,
        request: ChatRequest,
        provider_id: str = "auto",
        allow_cloud: bool = True,
    ) -> ChatResponse:
        prov = self.select_provider(provider_id, allow_cloud=allow_cloud)
        try:
            resp = await prov.generate(request)
            self.usage_tracker.record(
                provider=resp.provider,
                model=resp.model,
                capability="chat",
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                latency_ms=resp.latency_ms,
                status="ok",
            )
            return resp
        except Exception:
            self.usage_tracker.record(
                provider=prov.provider_id,
                model=request.model or prov.default_model,
                capability="chat",
                status="error",
            )
            raise

    async def stream(
        self,
        request: ChatRequest,
        provider_id: str = "auto",
        allow_cloud: bool = True,
    ) -> AsyncIterator[StreamChunk]:
        prov = self.select_provider(provider_id, allow_cloud=allow_cloud)
        async for chunk in prov.stream(request):
            if chunk.done:
                self.usage_tracker.record(
                    provider=prov.provider_id,
                    model=chunk.model or prov.default_model,
                    capability="chat_stream",
                    input_tokens=chunk.input_tokens,
                    output_tokens=chunk.output_tokens,
                    status="ok",
                )
            yield chunk
