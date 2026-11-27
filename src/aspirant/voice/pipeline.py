"""Full-duplex voice interaction coordinator with auto-discovery, recovery, barge-in, wake word, and TTS/STT."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import threading
import time
from typing import Any

import numpy as np
import sounddevice as sd

from aspirant.core.chat_service import ChatService
from aspirant.core.events import EventBus
from aspirant.core.telemetry import invalidate_audio_cache, probe_audio_devices
from aspirant.personality.language_detect import detect_language
from aspirant.providers.stt_providers import STTRouter
from aspirant.providers.tts_providers import TTSResult, TTSRouter
from aspirant.security.audit import AuditLogger
from aspirant.security.permissions import Permission, PermissionManager
from aspirant.voice.audio_io import (
    FRAME_SAMPLES,
    SAMPLE_RATE,
    AudioPlaybackController,
    NoiseAdaptiveVAD,
    pcm16_to_wav_bytes,
)
from aspirant.voice.diagnostics import AudioDiagnosticsManager, get_diagnostics_manager
from aspirant.voice.gemini_live import GeminiLiveSessionManager
from aspirant.voice.profiles import VoiceConfig
from aspirant.voice.wakeword import build_voice_confirmation, match_wake_word


def _resample_int16_to_16k(mono_i16: np.ndarray, src_rate: int) -> bytes:
    """Resample 30ms int16 capture buffer from native rate (e.g. 48kHz/44.1kHz) to 16kHz 480 samples."""
    if src_rate == SAMPLE_RATE and mono_i16.size == FRAME_SAMPLES:
        return mono_i16.tobytes()
    src_f = mono_i16.astype(np.float32)
    x_old = np.linspace(0.0, 1.0, num=src_f.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=FRAME_SAMPLES, endpoint=False)
    resampled = np.interp(x_new, x_old, src_f)
    return np.clip(np.rint(resampled), -32768, 32767).astype(np.int16).tobytes()


class VoiceAssistantEngine:
    """Manages microphone discovery, auto-recovery, listening modes, STT->Chat->Female TTS, and barge-in."""

    def __init__(
        self,
        chat_service: ChatService,
        tts_router: TTSRouter,
        stt_router: STTRouter,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
        event_bus: EventBus,
        diagnostics: AudioDiagnosticsManager | None = None,
    ) -> None:
        self.chat_service = chat_service
        self.tts_router = tts_router
        self.stt_router = stt_router
        self.permissions = permissions
        self.audit_logger = audit_logger
        self.event_bus = event_bus
        self.diagnostics = diagnostics or get_diagnostics_manager()

        self.config = VoiceConfig()
        self.state = "idle"  # idle | armed_wake_word | listening | transcribing | thinking | speaking
        self.conversation_id: str | None = None
        self.persona_id: str = "companion"
        self.last_transcript: str = ""
        self.last_reply: str = ""
        self.last_language: str = "en"

        self.muted: bool = False
        self.vad_active: bool = False
        self.last_rms_db: float = -90.0
        self.voice_activity_percent: int = 0

        self.playback = AudioPlaybackController()
        self.gemini_live = GeminiLiveSessionManager(
            permissions=permissions,
            audit_logger=audit_logger,
            event_bus=event_bus,
        )
        self._vad = NoiseAdaptiveVAD()
        self._capture_stop = threading.Event()
        self._capture_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        # Register Emergency STOP hook so kill switch immediately cuts mic & speaker
        self.permissions.register_stop_hook(self.emergency_halt)

    def emergency_halt(self) -> None:
        self.playback.interrupt()
        self.gemini_live.stop()
        self.stop_listening()

    def set_muted(self, muted: bool) -> dict[str, Any]:
        self.muted = bool(muted)
        if self.muted:
            self.vad_active = False
            self.voice_activity_percent = 0
        self.event_bus.publish("voice.mute", {"muted": self.muted})
        return self.status()

    def status(self) -> dict[str, Any]:
        audio = probe_audio_devices()
        mic_connected = bool(audio.get("mic_available", False))
        # Prefer explicit diagnostics manager state if selected cleanly
        active_name = audio.get("active_device_name") or "None"
        active_idx = audio.get("active_device_index")
        active_type = audio.get("active_device_type", "unknown")
        driver_status = audio.get("driver_status", "Unavailable")
        sample_rate = int(audio.get("sample_rate", 0))
        perm_granted = bool(audio.get("permission_granted", True))

        if self.muted:
            listening_indicator = "muted"
        elif self.state in {"listening", "transcribing"}:
            listening_indicator = "listening"
        elif self.state == "armed_wake_word":
            listening_indicator = "wake_word"
        else:
            listening_indicator = self.config.activation_mode

        asr_status = "unavailable"
        if mic_connected and not self.muted:
            asr_status = (
                "listening"
                if self.state in {"listening", "transcribing", "armed_wake_word"}
                else "ready"
            )
        elif mic_connected and self.muted:
            asr_status = "muted"

        return {
            "state": self.state,
            "persona_id": self.persona_id,
            "conversation_id": self.conversation_id,
            "last_transcript": self.last_transcript,
            "last_reply": self.last_reply,
            "last_language": self.last_language,
            "is_playing": self.playback.is_playing,
            "gemini_live_active": self.gemini_live.is_active,
            "config": asdict(self.config),
            # Voice Control Dashboard & Mic Telemetry fields
            "listening_mode": listening_indicator,
            "wake_word_armed": self.config.activation_mode == "wake_word" or self.state == "armed_wake_word",
            "asr_status": asr_status,
            "vad_active": self.vad_active,
            "rms_db": self.last_rms_db,
            "voice_activity_percent": self.voice_activity_percent,
            "noise_suppression_on": self.config.noise_suppression,
            "muted": self.muted,
            "mic_connected": mic_connected,
            "mic_status": "MIC: CONNECTED" if mic_connected else "MIC: NOT FOUND",
            "current_device_index": active_idx,
            "current_device_name": active_name,
            "current_device_type": active_type,
            "driver_status": driver_status,
            "sample_rate": sample_rate,
            "permission_granted": perm_granted,
            "last_test_result": self.diagnostics.last_test_result,
            "issues": audio.get("issues_detected", []),
        }

    def update_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        for key, value in updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self._vad.noise_suppression = self.config.noise_suppression
        self.event_bus.publish("voice.config", self.status())
        return self.status()

    def _set_state(self, new_state: str) -> None:
        self.state = new_state
        self.event_bus.publish("voice.state", self.status())

    def interrupt_speech(self) -> dict[str, Any]:
        """Support instant voice interruption (barge-in)."""
        interrupted = self.playback.interrupt()
        if self.state == "speaking":
            self._set_state("listening" if self.config.activation_mode != "idle" else "idle")
        return {"interrupted": interrupted, "state": self.state}

    async def synthesize_only(self, text: str, language_code: str = "auto") -> TTSResult:
        """Synthesize female speech audio bytes for UI preview or direct voice output."""
        lang = detect_language(text).code if language_code == "auto" else language_code
        allow_cloud = self.permissions.is_allowed(Permission.NETWORK)
        return await self.tts_router.synthesize(
            text=text,
            language_code=lang,
            config=self.config,
            allow_cloud=allow_cloud,
        )

    async def process_spoken_text(
        self,
        transcript: str,
        provider_id: str = "auto",
        speak_output: bool = True,
    ) -> dict[str, Any]:
        """Handle transcribed text through ChatService and optionally speak the female response."""
        self.permissions.require(Permission.READ, "Process voice command", category="voice")
        self.last_transcript = transcript.strip()
        confirmation = build_voice_confirmation(self.last_transcript)
        self.event_bus.publish(
            "voice.transcript.final",
            {
                "transcript": self.last_transcript,
                "confirmation": confirmation,
                "state": "thinking",
            },
        )
        self._set_state("thinking")

        result = await self.chat_service.send_message(
            user_text=self.last_transcript,
            conversation_id=self.conversation_id,
            persona_id=self.persona_id,
            provider_id=provider_id,
        )
        self.conversation_id = result["conversation_id"]
        self.persona_id = result["persona"]
        reply_text = str(result["message"]["content"])
        lang_code = str(result["detected_language"]["code"])
        self.last_reply = reply_text
        self.last_language = lang_code

        tts_info: dict[str, Any] | None = None
        if speak_output and reply_text.strip():
            self._set_state("speaking")
            tts = await self.synthesize_only(reply_text, language_code=lang_code)
            tts_info = {
                "provider": tts.provider,
                "voice": tts.voice_name,
                "mime_type": tts.mime_type,
                "latency_ms": round(tts.latency_ms, 1),
            }
            await asyncio.to_thread(self.playback.play_audio_bytes, tts.audio_bytes)

        next_state = (
            "armed_wake_word"
            if self.config.activation_mode == "wake_word"
            else ("listening" if self.config.activation_mode == "hands_free" else "idle")
        )
        self._set_state(next_state)
        payload = {
            "transcript": self.last_transcript,
            "confirmation": confirmation,
            "reply": reply_text,
            "language": result["detected_language"],
            "persona": self.persona_id,
            "tts": tts_info,
        }
        self.event_bus.publish("voice.turn_completed", payload)
        return payload

    async def process_audio_bytes(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
        provider_id: str = "auto",
        speak_output: bool = True,
        require_wake_word: bool = False,
    ) -> dict[str, Any]:
        """Transcribe recorded audio, check wake word if required, and answer with female TTS."""
        self.permissions.require(Permission.READ, "Transcribe voice audio", category="voice")
        self._set_state("transcribing")
        allow_cloud = self.permissions.is_allowed(Permission.NETWORK)
        stt = await self.stt_router.transcribe(
            audio_bytes=audio_bytes,
            provider_id=self.config.stt_provider,
            allow_cloud=allow_cloud,
            mime_type=mime_type,
        )
        text = stt.text.strip()
        self.event_bus.publish(
            "voice.transcript.partial",
            {"transcript": text, "language": stt.language, "provider": stt.provider},
        )
        if not text:
            self._set_state("idle" if self.config.activation_mode == "idle" else "armed_wake_word")
            return {"ignored": True, "reason": "No intelligible speech detected.", "stt": asdict(stt)}

        if require_wake_word:
            matched, command = match_wake_word(text)
            if not matched:
                self._set_state("armed_wake_word")
                return {"ignored": True, "reason": "Wake word 'Hey Aspirant' not heard.", "transcript": text}
            text = command or "Hello Aspirant"

        res = await self.process_spoken_text(
            transcript=text,
            provider_id=provider_id,
            speak_output=speak_output,
        )
        res["stt"] = asdict(stt)
        return res

    def start_listening(self, mode: str, loop: asyncio.AbstractEventLoop) -> dict[str, Any]:
        """Explicitly arm Push-to-Talk, Wake Word ('Hey Aspirant'), or Hands-Free mode."""
        self.permissions.require(Permission.READ, f"Activate microphone ({mode})", category="voice")
        self.stop_listening()
        self._loop = loop
        self.muted = False
        self.config.activation_mode = mode
        self._capture_stop.clear()

        # Auto-discover or auto-recover best microphone before spawning capture loop
        diag = self.diagnostics.discover()
        if not diag.get("mic_available") or not diag.get("active_device"):
            rec = self.diagnostics.recover()
            invalidate_audio_cache()
            if rec.get("status") != "recovered":
                self._set_state("idle")
                self.config.activation_mode = "idle"
                raise RuntimeError(
                    rec.get("error") or "No usable microphone found after automatic recovery."
                )

        self._set_state("armed_wake_word" if mode == "wake_word" else "listening")
        self.audit_logger.log(
            category="voice",
            action=f"Microphone activated ({mode} mode)",
            permission="READ",
            decision="started",
            status="ok",
        )
        self._capture_thread = threading.Thread(
            target=self._capture_loop, args=(mode,), name="aspirant-mic", daemon=True
        )
        self._capture_thread.start()
        return self.status()

    def stop_listening(self) -> dict[str, Any]:
        """Stop microphone capture and release optional heavy local STT memory."""
        self.gemini_live.stop()
        self._capture_stop.set()
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=1.5)
        self._capture_thread = None
        self.config.activation_mode = "idle"
        self.vad_active = False
        self.voice_activity_percent = 0
        self.stt_router.local.unload()
        self._set_state("idle")
        self.audit_logger.log(
            category="voice",
            action="Microphone deactivated",
            permission="READ",
            decision="stopped",
            status="ok",
        )
        return self.status()

    def _open_best_capture_stream(self) -> tuple[sd.RawInputStream, int, int]:
        """Negotiate device + sample rate (16kHz preferred, else native e.g. 48kHz) with auto-recovery."""
        snap = self.diagnostics.discover()
        candidates: list[dict[str, Any]] = []
        active = snap.get("active_device")
        if active:
            candidates.append(active)
        for dev in snap.get("input_devices", []):
            if dev.get("usable", True) and dev not in candidates:
                candidates.append(dev)

        for pass_num in range(2):
            for cand in candidates:
                idx = cand["index"]
                def_sr = int(cand.get("default_samplerate", SAMPLE_RATE))
                rates = [r for r in (SAMPLE_RATE, def_sr, 48000, 44100) if r and r > 0]
                for sr in dict.fromkeys(rates):
                    block = max(256, int(sr * 0.03))
                    try:
                        stream = sd.RawInputStream(
                            device=idx,
                            samplerate=sr,
                            blocksize=block,
                            channels=1,
                            dtype="int16",
                        )
                        stream.start()
                        return stream, sr, block
                    except Exception:
                        continue
            if pass_num == 0:
                rec = self.diagnostics.recover()
                invalidate_audio_cache()
                if rec.get("status") == "recovered" and rec.get("device"):
                    candidates = [rec["device"]]
                    continue
            break
        raise RuntimeError("No openable microphone input stream found after recovery attempts.")

    def _capture_loop(self, mode: str) -> None:
        """Continuously read 30ms PCM frames, perform VAD + barge-in, and dispatch utterances."""
        voiced_frames: list[bytes] = []
        silence_frames = 0
        in_speech = False
        awake_until = time.monotonic() + (30.0 if mode == "hands_free" else 0.0)
        stream: sd.RawInputStream | None = None

        try:
            stream, cap_sr, block_samples = self._open_best_capture_stream()
            while not self._capture_stop.is_set():
                try:
                    data, _overflow = stream.read(block_samples)
                except Exception:
                    # Hot-unplug / driver reset: automatically recover and re-open stream
                    try:
                        stream.close()
                    except Exception:
                        pass
                    self.diagnostics.recover()
                    invalidate_audio_cache()
                    stream, cap_sr, block_samples = self._open_best_capture_stream()
                    continue

                if self.muted:
                    self.vad_active = False
                    self.last_rms_db = -90.0
                    self.voice_activity_percent = 0
                    self.event_bus.publish("voice.level", {"rms_db": -90.0, "speech": False, "muted": True})
                    continue

                raw_i16 = np.frombuffer(bytes(data), dtype=np.int16)
                frame = _resample_int16_to_16k(raw_i16, cap_sr)
                speech, rms_db = self._vad.is_speech(frame)
                self.vad_active = speech
                self.last_rms_db = round(rms_db, 1)
                self.voice_activity_percent = max(0, min(100, int(round(((rms_db + 75.0) / 75.0) * 100.0))))
                self.event_bus.publish(
                    "voice.level",
                    {
                        "rms_db": self.last_rms_db,
                        "speech": speech,
                        "percent": self.voice_activity_percent,
                        "muted": False,
                    },
                )

                if speech:
                    # Barge-in: user started speaking while assistant was talking
                    if self.playback.is_playing:
                        self.playback.interrupt()
                    in_speech = True
                    silence_frames = 0
                    voiced_frames.append(frame)
                elif in_speech:
                    voiced_frames.append(frame)
                    silence_frames += 1
                    if silence_frames >= 22 or len(voiced_frames) >= 400:
                        pcm_blob = b"".join(voiced_frames)
                        voiced_frames.clear()
                        in_speech = False
                        silence_frames = 0
                        wav_bytes = pcm16_to_wav_bytes(pcm_blob)
                        need_wake = mode == "wake_word" and time.monotonic() > awake_until
                        if self._loop and not self._loop.is_closed():
                            fut = asyncio.run_coroutine_threadsafe(
                                self.process_audio_bytes(
                                    wav_bytes,
                                    require_wake_word=need_wake,
                                    speak_output=True,
                                ),
                                self._loop,
                            )
                            try:
                                res = fut.result(timeout=45.0)
                                if not res.get("ignored"):
                                    awake_until = time.monotonic() + 25.0
                            except Exception:
                                pass
                        if mode == "push_to_talk":
                            break
        except Exception as exc:
            self.event_bus.publish("voice.error", {"detail": str(exc)})
            self._set_state("idle")
        finally:
            self.vad_active = False
            self.voice_activity_percent = 0
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
