"""Full-duplex voice interaction coordinator with barge-in, wake word, and TTS/STT routing."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import threading
import time
from typing import Any

import sounddevice as sd

from aspirant.core.chat_service import ChatService
from aspirant.core.events import EventBus
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
from aspirant.voice.gemini_live import GeminiLiveSessionManager
from aspirant.voice.profiles import VoiceConfig
from aspirant.voice.wakeword import match_wake_word


class VoiceAssistantEngine:
    """Manages microphone listening modes, STT->Chat->Female TTS turns, and interruption."""

    def __init__(
        self,
        chat_service: ChatService,
        tts_router: TTSRouter,
        stt_router: STTRouter,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
        event_bus: EventBus,
    ) -> None:
        self.chat_service = chat_service
        self.tts_router = tts_router
        self.stt_router = stt_router
        self.permissions = permissions
        self.audit_logger = audit_logger
        self.event_bus = event_bus

        self.config = VoiceConfig()
        self.state = "idle"  # idle | armed_wake_word | listening | transcribing | thinking | speaking
        self.conversation_id: str | None = None
        self.persona_id: str = "companion"
        self.last_transcript: str = ""
        self.last_reply: str = ""
        self.last_language: str = "en"

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

    def status(self) -> dict[str, Any]:
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
        self.config.activation_mode = mode
        self._capture_stop.clear()
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

    def _capture_loop(self, mode: str) -> None:
        """Continuously read 30ms PCM frames, perform VAD + barge-in, and dispatch utterances."""
        voiced_frames: list[bytes] = []
        silence_frames = 0
        in_speech = False
        awake_until = time.monotonic() + (30.0 if mode == "hands_free" else 0.0)

        try:
            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=FRAME_SAMPLES,
                channels=1,
                dtype="int16",
            ) as stream:
                while not self._capture_stop.is_set():
                    data, _overflow = stream.read(FRAME_SAMPLES)
                    frame = bytes(data)
                    speech, rms_db = self._vad.is_speech(frame)
                    self.event_bus.publish("voice.level", {"rms_db": round(rms_db, 1), "speech": speech})

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
