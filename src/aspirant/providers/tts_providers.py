"""Female TTS providers: edge-tts neural Indian voices, Gemini 3.8 TTS, and offline SAPI5."""

from __future__ import annotations

import asyncio
import base64
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import edge_tts
from google import genai

from aspirant.voice.profiles import (
    EMOTION_STYLE_PROMPTS,
    VoiceConfig,
    format_edge_prosody,
    resolve_edge_voice,
    resolve_gemini_voice,
)


@dataclass(frozen=True, slots=True)
class TTSResult:
    audio_bytes: bytes
    mime_type: str
    voice_name: str
    provider: str
    latency_ms: float


class EdgeFemaleTTSProvider:
    """Free natural female & male Indian neural voices via Microsoft Edge TTS."""

    provider_id = "edge-tts"

    async def synthesize(
        self, text: str, language_code: str, config: VoiceConfig
    ) -> TTSResult:
        t0 = time.perf_counter()
        voice = resolve_edge_voice(language_code, config.voice_gender, config.voice_override)
        rate_str, pitch_str = format_edge_prosody(config.speed, config.pitch_hz)
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate_str,
            pitch=pitch_str,
        )
        chunks: list[bytes] = []
        async for msg in communicate.stream():
            if msg.get("type") == "audio":
                chunks.append(msg["data"])
        audio_bytes = b"".join(chunks)
        if not audio_bytes:
            raise RuntimeError("edge-tts returned empty audio stream.")
        return TTSResult(
            audio_bytes=audio_bytes,
            mime_type="audio/mpeg",
            voice_name=voice,
            provider=self.provider_id,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )


class GeminiFemaleTTSProvider:
    """Expressive female speech synthesis via Gemini 3.8 Flash TTS."""

    provider_id = "gemini"
    model = "gemini-3.8-flash-tts"

    def __init__(self, api_key: str | None) -> None:
        self.api_key = (api_key or "").strip()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def synthesize(
        self, text: str, language_code: str, config: VoiceConfig
    ) -> TTSResult:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured for Gemini TTS.")
        t0 = time.perf_counter()
        voice = resolve_gemini_voice(config.voice_gender, config.voice_override)
        gender_label = "male" if config.voice_gender.strip().lower() == "male" else "female"
        style_desc = f"{gender_label}, {EMOTION_STYLE_PROMPTS.get(config.emotion, EMOTION_STYLE_PROMPTS['friendly'])}"
        client = genai.Client(api_key=self.api_key, http_options={"api_version": "v1beta"})
        interaction = await asyncio.wait_for(
            client.aio.interactions.create(
                model=self.model,
                input=[
                    {
                        "type": "user_input",
                        "content": [
                            {
                                "type": "text",
                                "text": text,
                                "annotations": [
                                    {
                                        "type": "speech_metadata",
                                        "style": f"{style_desc}; speaking speed {config.speed:.2f}x",
                                    }
                                ],
                            }
                        ],
                    }
                ],
                response_format={"type": "audio"},
                generation_config={"speech_config": [{"voice": voice}]},
            ),
            timeout=30.0,
        )
        out_audio = getattr(interaction, "output_audio", None)
        if not out_audio or not getattr(out_audio, "data", None):
            raise RuntimeError("Gemini TTS did not return audio data.")
        raw_bytes = base64.b64decode(out_audio.data)
        return TTSResult(
            audio_bytes=raw_bytes,
            mime_type=getattr(out_audio, "mime_type", "audio/wav") or "audio/wav",
            voice_name=voice,
            provider=self.provider_id,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )


class WindowsSAPITTSProvider:
    """100% offline Windows SAPI5 female voice fallback."""

    provider_id = "sapi5"

    async def synthesize(
        self, text: str, language_code: str, config: VoiceConfig
    ) -> TTSResult:
        if sys.platform != "win32":
            raise RuntimeError("Windows SAPI5 is only available on Windows.")
        t0 = time.perf_counter()

        def _render_sync() -> bytes:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                wav_path = Path(tf.name)
            try:
                rate_val = max(-5, min(5, int(round((config.speed - 1.0) * 10))))
                safe_text = text.replace("'", "''")
                sapi_gender = "Male" if config.voice_gender.strip().lower() == "male" else "Female"
                ps_script = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$f = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Gender -eq '{sapi_gender}' }} | Select-Object -First 1; "
                    "if ($f) { $s.SelectVoice($f.VoiceInfo.Name) }; "
                    f"$s.Rate = {rate_val}; "
                    f"$s.SetOutputToWaveFile('{wav_path}'); "
                    f"$s.Speak('{safe_text}'); "
                    "$s.Dispose();"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    check=True,
                    capture_output=True,
                    timeout=20,
                )
                return wav_path.read_bytes()
            finally:
                wav_path.unlink(missing_ok=True)

        wav_bytes = await asyncio.to_thread(_render_sync)
        gender_title = "Male" if config.voice_gender.strip().lower() == "male" else "Female"
        return TTSResult(
            audio_bytes=wav_bytes,
            mime_type="audio/wav",
            voice_name=f"Windows SAPI5 {gender_title}",
            provider=self.provider_id,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )


class TTSRouter:
    """Routes female speech synthesis across configured providers with offline fallback."""

    def __init__(self, gemini_api_key: str | None = None) -> None:
        self.edge = EdgeFemaleTTSProvider()
        self.gemini = GeminiFemaleTTSProvider(gemini_api_key)
        self.sapi5 = WindowsSAPITTSProvider()

    def update_gemini_key(self, gemini_api_key: str | None) -> None:
        self.gemini.api_key = (gemini_api_key or "").strip()

    async def synthesize(
        self,
        text: str,
        language_code: str,
        config: VoiceConfig,
        allow_cloud: bool = True,
    ) -> TTSResult:
        requested = config.tts_provider
        if not allow_cloud or requested == "sapi5":
            return await self.sapi5.synthesize(text, language_code, config)

        if requested == "gemini":
            if self.gemini.is_configured():
                try:
                    return await self.gemini.synthesize(text, language_code, config)
                except Exception:
                    pass
            # Fallback cleanly to edge-tts then SAPI5
            try:
                return await self.edge.synthesize(text, language_code, config)
            except Exception:
                return await self.sapi5.synthesize(text, language_code, config)

        if requested == "auto":
            if self.gemini.is_configured():
                try:
                    return await self.gemini.synthesize(text, language_code, config)
                except Exception:
                    pass
            try:
                return await self.edge.synthesize(text, language_code, config)
            except Exception:
                return await self.sapi5.synthesize(text, language_code, config)

        if requested == "edge-tts":
            try:
                return await self.edge.synthesize(text, language_code, config)
            except Exception:
                if self.gemini.is_configured():
                    try:
                        return await self.gemini.synthesize(text, language_code, config)
                    except Exception:
                        pass
                return await self.sapi5.synthesize(text, language_code, config)

        return await self.sapi5.synthesize(text, language_code, config)
