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

    for phrase, expected_tail in (
        ("Hey Aspirant, create a FastAPI project.", "create a FastAPI project"),
        ("Aspirant, explain Docker.", "explain Docker"),
        ("Hello Aspirant deploy this app", "deploy this app"),
    ):
        ok, tail = match_wake_word(phrase)
        assert ok is True
        assert expected_tail.lower() in tail.lower()

    matched_unrelated, _ = match_wake_word("What does an aspirant study for exams?")
    assert matched_unrelated is False

    matched_no, _ = match_wake_word("Open calculator please")
    assert matched_no is False

    from aspirant.voice.wakeword import build_voice_confirmation

    assert "Boss" in build_voice_confirmation("create a FastAPI project")
    assert "Preparing deployment steps" in build_voice_confirmation("deploy this app")

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


def test_desktop_microphone_classification_ranking_and_api_endpoints(tmp_path: Path) -> None:
    from aspirant.ui.app_window import AspirantMainWindow
    from aspirant.ui.views.voice_view import MicSetupWizard
    from aspirant.voice.diagnostics import (
        auto_select_best_microphone,
        classify_device_type,
        clean_device_display_name,
    )

    # 1. Classification across USB, Bluetooth, Laptop Integrated, and Virtual
    assert classify_device_type("Blue Yeti USB Microphone", "Windows WASAPI") == "usb"
    assert (
        classify_device_type(
            "Headset (@System32\\drivers\\bthhfenum.sys,#2;%1 Hands-Free%0\r\n;(AirBass Headphone))",
            "Windows WDM-KS",
        )
        == "bluetooth"
    )
    assert (
        classify_device_type(
            "Microphone Array (Intel® Smart Sound Technology for Digital Microphones)",
            "Windows WASAPI",
        )
        == "integrated"
    )
    assert classify_device_type("Stereo Mix (Realtek(R) Audio)", "Windows WASAPI") == "virtual"
    assert classify_device_type("Microsoft Sound Mapper - Input", "MME") == "virtual"
    assert (
        clean_device_display_name(
            "Headset (@System32\\drivers\\bthhfenum.sys,#2;%1 Hands-Free%0\r\n;(AirBass Headphone))",
            "Windows WDM-KS",
        )
        == "AirBass Headphone (Bluetooth Hands-Free) (WDM-KS)"
    )

    # 2. Best microphone selection: usable non-WDM-KS physical mics beat WDM-KS standby & virtual
    candidates = [
        {"index": 0, "name": "Stereo Mix", "device_type": "virtual", "hostapi": "Windows WASAPI", "usable": True},
        {"index": 1, "name": "Offline BT WDM", "device_type": "bluetooth", "hostapi": "Windows WDM-KS", "usable": False},
        {"index": 2, "name": "Microphone Array", "device_type": "integrated", "hostapi": "Windows WASAPI", "usable": True},
        {"index": 3, "name": "Active BT Headset", "device_type": "bluetooth", "hostapi": "MME", "usable": True},
        {"index": 4, "name": "Studio USB Mic", "device_type": "usb", "hostapi": "Windows WASAPI", "usable": True},
    ]
    assert auto_select_best_microphone(candidates)["index"] == 4
    assert auto_select_best_microphone(candidates[:-1])["index"] == 3
    assert auto_select_best_microphone(candidates[:3])["index"] == 2
    assert auto_select_best_microphone(candidates[:2])["index"] == 0

    # 3. Desktop FastAPI mic diagnostics, test, change, mute, recover endpoints
    settings = AppSettings(ASPIRANT_DATA_DIR=tmp_path / "data")
    container = build_container(settings)
    app = create_app(settings=settings, container=container)
    headers = {"Authorization": f"Bearer {container.api_token}"}

    with TestClient(app) as client:
        devs = client.get("/api/v1/voice/diagnostics/devices", headers=headers)
        assert devs.status_code == 200
        djson = devs.json()
        assert {"mic_available", "mic_status", "input_devices", "permission", "repair_guidance"}.issubset(djson)

        t_ok = client.post(
            "/api/v1/voice/diagnostics/test-mic",
            headers=headers,
            json={"samples": [0.1, -0.1, 0.12, -0.08] * 8},
        )
        assert t_ok.status_code == 200 and t_ok.json()["signal_quality"] == "ok"

        t_mute = client.post(
            "/api/v1/voice/diagnostics/test-mic",
            headers=headers,
            json=[0.0, 0.0, 0.0, 0.0] * 4,
        )
        assert t_mute.status_code == 200 and t_mute.json()["signal_quality"] == "muted"

        muted = client.post("/api/v1/voice/mute", headers=headers, json={"muted": True})
        assert muted.status_code == 200 and muted.json()["muted"] is True
        unmuted = client.post("/api/v1/voice/mute", headers=headers, json={"muted": False})
        assert unmuted.status_code == 200 and unmuted.json()["muted"] is False

        if djson["input_devices"]:
            idx = djson["input_devices"][0]["index"]
            ch = client.post("/api/v1/voice/diagnostics/change-mic", headers=headers, json={"device_index": idx})
            assert ch.status_code == 200 and ch.json()["status"] == "changed"

        rec = client.post("/api/v1/voice/diagnostics/recover", headers=headers)
        assert rec.status_code == 200 and rec.json()["status"] in {"recovered", "no_devices"}

    # 4. PySide6 UI widgets: VoiceControlDashboard, MicDiagnosticsPanel, TopBar recovery, MicSetupWizard
    qt = QApplication.instance() or QApplication([])
    view = VoiceAssistantView(api_client=None)  # type: ignore[arg-type]
    view.voice_dashboard.update_status({
        "mic_connected": True,
        "listening_mode": "listening",
        "wake_word_armed": True,
        "asr_status": "ready",
        "vad_active": True,
        "voice_activity_percent": 62,
        "rms_db": -28.0,
        "noise_suppression_on": True,
        "current_device_name": "Studio USB Mic",
        "current_device_type": "usb",
    })
    assert "CONNECTED" in view.voice_dashboard.conn_badge.text() or "Connected" in view.voice_dashboard.conn_badge.text()
    assert view.voice_dashboard.vad_meter.value() == 62
    view.mic_panel._on_devices({
        "mic_available": False,
        "input_devices": [],
        "issues_detected": ["No active mic"],
        "repair_guidance": ["Reconnect Microphone"],
        "permission": {"granted": True},
    })
    assert "NOT FOUND" in view.mic_panel.status_pill.text()
    view.mic_panel._on_recover({
        "status": "recovered",
        "device": {
            "index": 9,
            "display_name": "Microphone Array (WASAPI)",
            "device_type": "integrated",
            "driver_status": "Available (Windows WASAPI)",
            "default_samplerate": 48000,
        },
        "steps_attempted": ["1. Rescanning", "4. Connected"],
    })
    assert "CONNECTED" in view.mic_panel.status_pill.text()
    view.shutdown()

    wiz = MicSetupWizard(api_client=None, auto_run=False)  # type: ignore[arg-type]
    wiz._run_auto_check()
    assert "Permission:" in wiz.perm_lbl.text()
    wiz.close()

    class _StubClient:
        def get_overview(self): return {"telemetry": {"audio": {}}, "security": {}, "voice": {}}
        def get_audit_logs(self, **_kw): return {"items": []}
        def recover_microphone(self): return {"status": "no_devices"}
    win = AspirantMainWindow(api_client=_StubClient())  # type: ignore[arg-type]
    win._apply_top_mic_status(False, "")
    assert "NOT FOUND" in win.top_mic_pill.text()
    win._on_mic_recovered({
        "status": "recovered",
        "device": {"display_name": "Microphone Array", "device_type": "integrated"},
    })
    assert "CONNECTED" in win.top_mic_pill.text()
    win.close()
    qt.processEvents()
