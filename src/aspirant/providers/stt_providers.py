"""Multi-provider speech-to-text (Gemini 3.5 Transcribe, OpenAI/Groq Whisper, lazy faster-whisper)."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import io
import time
from typing import Any

from google import genai
from openai import AsyncOpenAI


@dataclass(frozen=True, slots=True)
class STTResult:
    text: str
    language: str
    provider: str
    latency_ms: float


class GeminiSTTProvider:
    """Multilingual speech transcription using gemini-3.5-transcribe."""

    provider_id = "gemini"
    model = "gemini-3.5-transcribe"

    def __init__(self, api_key: str | None) -> None:
        self.api_key = (api_key or "").strip()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> STTResult:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured for Gemini STT.")
        t0 = time.perf_counter()
        client = genai.Client(api_key=self.api_key, http_options={"api_version": "v1beta"})
        b64 = base64.b64encode(audio_bytes).decode("ascii")
        resp = await asyncio.wait_for(
            client.aio.interactions.create(
                model=self.model,
                input=[{"type": "audio", "data": b64, "mime_type": mime_type}],
            ),
            timeout=30.0,
        )
        text = (getattr(resp, "output_text", None) or "").strip()
        return STTResult(
            text=text,
            language="auto",
            provider=self.provider_id,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )


class OpenAICompatSTTProvider:
    """Whisper transcription via OpenAI or Groq OpenAI-compatible audio endpoint."""

    def __init__(
        self,
        provider_id: str,
        api_key: str | None,
        base_url: str,
        model: str,
    ) -> None:
        self.provider_id = provider_id
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self.model = model

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> STTResult:
        if not self.api_key:
            raise RuntimeError(f"{self.provider_id} API key not configured.")
        t0 = time.perf_counter()
        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, timeout=30.0)
        ext = "wav" if "wav" in mime_type else "mp3"
        bio = io.BytesIO(audio_bytes)
        bio.name = f"speech.{ext}"
        res = await client.audio.transcriptions.create(model=self.model, file=bio)
        return STTResult(
            text=(getattr(res, "text", "") or "").strip(),
            language="auto",
            provider=self.provider_id,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )


class FasterWhisperLocalSTTProvider:
    """Lazy-loaded CPU int8 Whisper transcription to stay within 8 GB RAM budget."""

    provider_id = "faster-whisper"

    def __init__(self, model_size: str = "tiny") -> None:
        self.model_size = model_size
        self._model: Any = None

    def _ensure_loaded(self) -> Any:
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def unload(self) -> None:
        """Release model memory when voice assistant returns to idle."""
        self._model = None

    async def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> STTResult:
        t0 = time.perf_counter()

        def _run_sync() -> tuple[str, str]:
            model = self._ensure_loaded()
            segments, info = model.transcribe(io.BytesIO(audio_bytes), vad_filter=True)
            joined = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
            lang = getattr(info, "language", "auto") or "auto"
            return joined.strip(), lang

        text, lang = await asyncio.to_thread(_run_sync)
        return STTResult(
            text=text,
            language=lang,
            provider=self.provider_id,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )


class STTRouter:
    """Routes STT to Gemini/OpenAI/Groq when permitted, or local faster-whisper."""

    def __init__(
        self,
        gemini_key: str | None = None,
        openai_key: str | None = None,
        openai_url: str = "https://api.openai.com/v1",
        groq_key: str | None = None,
        whisper_model: str = "tiny",
    ) -> None:
        self.gemini = GeminiSTTProvider(gemini_key)
        self.openai = OpenAICompatSTTProvider("openai", openai_key, openai_url, "whisper-1")
        self.groq = OpenAICompatSTTProvider(
            "groq", groq_key, "https://api.groq.com/openai/v1", "whisper-large-v3-turbo"
        )
        self.local = FasterWhisperLocalSTTProvider(model_size=whisper_model)

    def refresh_keys(
        self,
        gemini_key: str | None,
        openai_key: str | None,
        openai_url: str,
        groq_key: str | None,
    ) -> None:
        self.gemini.api_key = (gemini_key or "").strip()
        self.openai.api_key = (openai_key or "").strip()
        self.openai.base_url = openai_url.rstrip("/")
        self.groq.api_key = (groq_key or "").strip()

    async def transcribe(
        self,
        audio_bytes: bytes,
        provider_id: str = "auto",
        allow_cloud: bool = True,
        mime_type: str = "audio/wav",
    ) -> STTResult:
        if not allow_cloud or provider_id == "faster-whisper":
            return await self.local.transcribe(audio_bytes, mime_type=mime_type)

        candidates: list[Any] = []
        if provider_id == "gemini":
            candidates = [self.gemini, self.local]
        elif provider_id == "groq":
            candidates = [self.groq, self.local]
        elif provider_id == "openai":
            candidates = [self.openai, self.local]
        else:
            for c in (self.gemini, self.groq, self.openai):
                if c.is_configured():
                    candidates.append(c)
            candidates.append(self.local)

        last_err: Exception | None = None
        for candidate in candidates:
            if hasattr(candidate, "is_configured") and not candidate.is_configured():
                continue
            try:
                return await candidate.transcribe(audio_bytes, mime_type=mime_type)
            except Exception as exc:
                last_err = exc
                continue
        raise RuntimeError(f"All STT providers failed: {last_err}")
