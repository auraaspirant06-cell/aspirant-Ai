"""Phase 3 tests for female TTS, wake-word detection, noise VAD, barge-in, and Voice API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncIterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fastapi.testclient import TestClient
from PySide6.QtWidgets import QApplication
import pytest

from aspirant.core.config import AppSettings
from aspirant.providers.base import (
    ChatRequest,
    ChatResponse,
    LLMProvider,
    ProviderHealth,
    StreamChunk,
)
from aspirant.providers.tts_providers import TTSResult, TTSRouter
from aspirant.server.app import build_container, create_app
from aspirant.ui.views.voice_view import VoiceAssistantView
from aspirant.voice.audio_io import (
    FRAME_SAMPLES,
    AudioPlaybackController,
    NoiseAdaptiveVAD,
    decode_audio_bytes_to_float32,
    pcm16_to_wav_bytes,
)
from aspirant.voice.gemini_live import build_live_config
from aspirant.voice.profiles import (
    VoiceConfig,
    format_edge_prosody,
    resolve_edge_female_voice,
)
from aspirant.voice.wakeword import match_wake_word


class _StubLLM(LLMProvider):
    provider_id = "gemini"
    display_name = "Stub Gemini"
    default_model = "gemini-4-hydrogen"
    mode = "cloud"

    def is_configured(self) -> bool:
        return True

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(self.provider_id, self.display_name, True, True)

    async def generate(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            text="Namaste, main Aspirant AI hoon. Teacher mode activate ho gaya hai.",
            provider=self.provider_id,
            model=self.default_model,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(delta_text="Namaste", done=True, provider=self.provider_id, model=self.default_model)


def test_female_voice_mapping_and_prosody() -> None:
    assert resolve_edge_female_voice("en") == "en-IN-NeerjaNeural"
    assert resolve_edge_female_voice("hi") == "hi-IN-SwaraNeural"
    assert resolve_edge_female_voice("ta") == "ta-IN-PallaviNeural"
    assert resolve_edge_female_voice("bn") == "bn-IN-TanishaaNeural"
    assert resolve_edge_female_voice("ur") == "ur-IN-GulNeural"
    assert format_edge_prosody(1.25, 10) == ("+25%", "+10Hz")
    assert format_edge_prosody(0.5, -50) == ("-25%", "-20Hz")


def test_wake_word_detection_and_noise_vad() -> None:
    matched, cmd = match_wake_word("Hey Aspirant switch to teacher mode")
    assert matched is True
    assert "switch to teacher mode" in cmd.lower()

    matched_hi, cmd_hi = match_wake_word("हे एस्पिरेंट आज का काम बताओ")
    assert matched_hi is True
    assert "आज का काम" in cmd_hi

    matched_no, _ = match_wake_word("Open calculator please")
    assert matched_no is False

    # Silence PCM frame should not trigger speech
    vad = NoiseAdaptiveVAD(aggressiveness=2, noise_suppression=True)
    silence = b"\x00\x00" * FRAME_SAMPLES
    is_sp, rms_db = vad.is_speech(silence)
    assert is_sp is False
    assert rms_db <= -80.0

    # WAV encode/decode round-trip
    wav_bytes = pcm16_to_wav_bytes(silence)
    arr, sr = decode_audio_bytes_to_float32(wav_bytes)
    assert sr == 16000
    assert arr.size == FRAME_SAMPLES


def test_barge_in_playback_interrupt_flag() -> None:
    ctrl = AudioPlaybackController()
    ctrl._is_playing = True
    assert ctrl.interrupt() is True
    assert ctrl._stop_event.is_set() is True


@pytest.mark.asyncio
async def test_offline_sapi5_female_tts_synthesis() -> None:
    from aspirant.providers.tts_providers import WindowsSAPITTSProvider

    provider = WindowsSAPITTSProvider()
    res = await provider.synthesize("Namaste, Aspirant AI is ready.", "en", VoiceConfig())
    assert res.mime_type == "audio/wav"
    assert len(res.audio_bytes) > 100
    assert res.audio_bytes[:4] == b"RIFF"


def test_voice_api_endpoints_and_ui(tmp_path: Path) -> None:
    settings = AppSettings(ASPIRANT_DATA_DIR=tmp_path / "data")
    container = build_container(settings)
    container.providers.register(_StubLLM())

    # Patch TTS router in test to avoid network reliance while verifying real endpoint contract
    async def _fake_tts(text: str, language_code: str, config: VoiceConfig, allow_cloud: bool = True):
        return TTSResult(
            audio_bytes=pcm16_to_wav_bytes(b"\x00\x00" * 480),
            mime_type="audio/wav",
            voice_name="en-IN-NeerjaNeural",
            provider="edge-tts",
            latency_ms=5.0,
        )

    container.tts_router.synthesize = _fake_tts  # type: ignore[method-assign]
    app = create_app(settings=settings, container=container)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {container.api_token}"}

    with client:
        st = client.get("/api/v1/voice/status", headers=headers)
        assert st.status_code == 200
        assert st.json()["state"] == "idle"

        cfg = client.post(
            "/api/v1/voice/config",
            headers=headers,
            json={"speed": 1.15, "pitch_hz": 5, "emotion": "cheerful"},
        )
        assert cfg.status_code == 200
        assert cfg.json()["config"]["speed"] == 1.15
        assert cfg.json()["config"]["emotion"] == "cheerful"

        speak = client.post(
            "/api/v1/voice/speak",
            headers=headers,
            json={"text": "नमस्ते दोस्त", "play_locally": False},
        )
        assert speak.status_code == 200
        assert speak.json()["voice"] == "en-IN-NeerjaNeural"

        turn = client.post(
            "/api/v1/voice/turn",
            headers=headers,
            json={"transcript": "switch to teacher mode", "speak_output": False},
        )
        assert turn.status_code == 200
        assert turn.json()["persona"] == "teacher"

        intr = client.post("/api/v1/voice/interrupt", headers=headers)
        assert intr.status_code == 200

    qt = QApplication.instance() or QApplication([])
    view = VoiceAssistantView(api_client=None)  # type: ignore[arg-type]
    view.update_status({"state": "speaking", "last_transcript": "Hey Aspirant", "last_reply": "Namaste"})
    assert "Speaking" in view.state_lbl.text()
    assert view.tts_combo.itemData(0) == "auto"
    view.shutdown()
    qt.processEvents()


@pytest.mark.asyncio
async def test_gemini_live_config_and_gemini_first_tts_routing() -> None:
    cfg = build_live_config(female_voice="Kore")
    assert cfg.speech_config.voice_config.prebuilt_voice_config.voice_name == "Kore"

    router = TTSRouter(gemini_api_key="dummy-key")
    called: list[str] = []

    async def _fake_gemini(text: str, language_code: str, config: VoiceConfig) -> TTSResult:
        called.append("gemini")
        return TTSResult(b"RIFFdata", "audio/wav", "Kore", "gemini", 4.0)

    async def _fake_edge(text: str, language_code: str, config: VoiceConfig) -> TTSResult:
        called.append("edge-tts")
        return TTSResult(b"mp3data", "audio/mpeg", "en-IN-NeerjaNeural", "edge-tts", 4.0)

    router.gemini.synthesize = _fake_gemini  # type: ignore[method-assign]
    router.edge.synthesize = _fake_edge  # type: ignore[method-assign]

    res = await router.synthesize("Hello", "en", VoiceConfig(tts_provider="auto"), allow_cloud=True)
    assert res.provider == "gemini"
    assert called == ["gemini"]

    # Without Gemini key, auto falls back smoothly to edge-tts
    router.update_gemini_key("")
    res2 = await router.synthesize("Hello", "en", VoiceConfig(tts_provider="auto"), allow_cloud=True)
    assert res2.provider == "edge-tts"
