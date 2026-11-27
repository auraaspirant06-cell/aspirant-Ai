"""Real-time bidirectional Gemini 3.8 Live audio/text session over WebSockets."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from google import genai
from google.genai import types
import numpy as np
import sounddevice as sd

from aspirant.core.events import EventBus
from aspirant.security.audit import AuditLogger
from aspirant.security.permissions import Permission, PermissionManager
from aspirant.voice.audio_io import FRAME_SAMPLES, SAMPLE_RATE


def build_live_config(
    system_instruction: str = (
        "You are ASPIRANT AI, an intelligent, warm, concise personal assistant with a natural female voice. "
        "Detect Hindi, English, Hinglish, and Indian languages automatically and respond in the same language without unnecessary translation."
    ),
    female_voice: str = "Kore",
) -> types.LiveConnectConfig:
    """Build a valid Gemini 3.8 Live configuration with female voice and live transcription."""
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=female_voice)
            )
        ),
        system_instruction=types.Content(parts=[types.Part(text=system_instruction)]),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


class GeminiLiveSessionManager:
    """Streams mic PCM (16 kHz) to Gemini 3.8 Live and plays 24 kHz response audio with barge-in."""

    model = "gemini-3.8-live"

    def __init__(
        self,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
        event_bus: EventBus,
    ) -> None:
        self.permissions = permissions
        self.audit_logger = audit_logger
        self.event_bus = event_bus
        self._stop_event = threading.Event()
        self._task: asyncio.Task[None] | None = None
        self._active = False
        self._playback_clear = threading.Event()

    @property
    def is_active(self) -> bool:
        return self._active

    def start(
        self,
        api_key: str | None,
        loop: asyncio.AbstractEventLoop,
        female_voice: str = "Kore",
    ) -> dict[str, Any]:
        self.permissions.require(Permission.READ, "Activate microphone for Gemini 3.8 Live", category="voice")
        self.permissions.require(Permission.NETWORK, "Connect Gemini 3.8 Live WebSocket", category="voice")
        if not (api_key or "").strip():
            raise RuntimeError("GEMINI_API_KEY is required for Gemini 3.8 Live mode.")

        self.stop()
        self._stop_event.clear()
        self._active = True
        self._task = asyncio.run_coroutine_threadsafe(
            self._run_session(api_key.strip(), female_voice), loop
        )  # type: ignore[assignment]
        self.audit_logger.log(
            category="voice",
            action=f"Started Gemini 3.8 Live session (voice={female_voice})",
            permission="NETWORK",
            decision="started",
            status="ok",
        )
        return {"active": True, "model": self.model, "voice": female_voice}

    def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        self._playback_clear.set()
        if self._task is not None:
            try:
                self._task.cancel()
            except Exception:
                pass
            self._task = None
        was_active = self._active
        self._active = False
        if was_active:
            self.audit_logger.log(
                category="voice",
                action="Stopped Gemini 3.8 Live session",
                permission="READ",
                decision="stopped",
                status="ok",
            )
        return {"active": False}

    async def _run_session(self, api_key: str, female_voice: str) -> None:
        client = genai.Client(api_key=api_key)
        config = build_live_config(female_voice=female_voice)
        audio_out_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=256)

        try:
            async with client.aio.live.connect(model=self.model, config=config) as session:
                self.event_bus.publish("voice.live_connected", {"model": self.model, "voice": female_voice})

                async def _send_mic() -> None:
                    with sd.RawInputStream(
                        samplerate=SAMPLE_RATE,
                        blocksize=FRAME_SAMPLES,
                        channels=1,
                        dtype="int16",
                    ) as mic_stream:
                        while not self._stop_event.is_set():
                            raw, _ = await asyncio.to_thread(mic_stream.read, FRAME_SAMPLES)
                            await session.send_realtime_input(
                                audio=types.Blob(data=bytes(raw), mime_type="audio/pcm;rate=16000")
                            )

                async def _play_speaker() -> None:
                    with sd.OutputStream(samplerate=24000, channels=1, dtype="int16") as spk:
                        while not self._stop_event.is_set():
                            try:
                                chunk = await asyncio.wait_for(audio_out_queue.get(), timeout=0.1)
                            except asyncio.TimeoutError:
                                continue
                            if self._playback_clear.is_set():
                                self._playback_clear.clear()
                                while not audio_out_queue.empty():
                                    try:
                                        audio_out_queue.get_nowait()
                                    except asyncio.QueueEmpty:
                                        break
                                continue
                            arr = np.frombuffer(chunk, dtype=np.int16).reshape(-1, 1)
                            await asyncio.to_thread(spk.write, arr)

                async def _receive() -> None:
                    async for response in session.receive():
                        if self._stop_event.is_set():
                            break
                        sc = getattr(response, "server_content", None)
                        if not sc:
                            continue
                        if getattr(sc, "interrupted", False):
                            self._playback_clear.set()
                        if getattr(sc, "input_transcription", None) and sc.input_transcription.text:
                            self.event_bus.publish(
                                "voice.live_transcript",
                                {"role": "user", "text": sc.input_transcription.text},
                            )
                        if getattr(sc, "output_transcription", None) and sc.output_transcription.text:
                            self.event_bus.publish(
                                "voice.live_transcript",
                                {"role": "assistant", "text": sc.output_transcription.text},
                            )
                        if getattr(sc, "model_turn", None) and sc.model_turn.parts:
                            for part in sc.model_turn.parts:
                                inline = getattr(part, "inline_data", None)
                                if inline and getattr(inline, "data", None):
                                    try:
                                        audio_out_queue.put_nowait(inline.data)
                                    except asyncio.QueueFull:
                                        pass

                await asyncio.gather(_send_mic(), _play_speaker(), _receive())
        except Exception as exc:
            self.event_bus.publish("voice.error", {"detail": f"Gemini 3.8 Live error: {exc}"})
        finally:
            self._active = False
