"""Audio encoding/decoding, adaptive noise floor VAD, and interruptible playback."""

from __future__ import annotations

import io
import math
import struct
import threading
import time
from typing import Callable
import wave

import numpy as np
import sounddevice as sd
import webrtcvad


SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # 480 samples = 960 bytes


def pcm16_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE, channels: int = 1) -> bytes:
    """Wrap raw 16-bit little-endian PCM bytes in a standard RIFF WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def decode_audio_bytes_to_float32(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    """Decode WAV or MP3 bytes into mono/stereo float32 numpy array + sample rate."""
    # Fast path for RIFF WAV
    if audio_bytes[:4] == b"RIFF":
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            sr = wf.getframerate()
            channels = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if channels > 1:
            arr = arr.reshape(-1, channels)
        return arr, sr

    # Decode MP3/AAC/OGG via PyAV (av)
    import av  # lazy import keeps idle RAM lean

    container = av.open(io.BytesIO(audio_bytes))
    stream = next((s for s in container.streams if s.type == "audio"), None)
    if stream is None:
        raise ValueError("No audio stream found in TTS output.")
    resampler = av.AudioResampler(format="flt", layout="mono", rate=24000)
    chunks: list[np.ndarray] = []
    for frame in container.decode(stream):
        resampled = resampler.resample(frame)
        for rf in resampled:
            chunks.append(rf.to_ndarray().reshape(-1))
    if not chunks:
        return np.zeros(0, dtype=np.float32), 24000
    return np.concatenate(chunks).astype(np.float32), 24000


def compute_rms_db(pcm_bytes: bytes) -> float:
    """Compute RMS level in dBFS for 16-bit PCM bytes."""
    if not pcm_bytes:
        return -90.0
    arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    if arr.size == 0:
        return -90.0
    rms = float(np.sqrt(np.mean(arr * arr)) / 32768.0)
    if rms <= 1e-6:
        return -90.0
    return 20.0 * math.log10(rms)


class NoiseAdaptiveVAD:
    """Combines WebRTC VAD with adaptive ambient noise floor tracking."""

    def __init__(self, aggressiveness: int = 2, noise_suppression: bool = True) -> None:
        self._vad = webrtcvad.Vad(max(0, min(3, aggressiveness)))
        self.noise_suppression = noise_suppression
        self._noise_floor_db = -55.0

    def is_speech(self, pcm_frame: bytes) -> tuple[bool, float]:
        """Classify a 30ms 16kHz PCM16 frame as speech or background noise."""
        rms_db = compute_rms_db(pcm_frame)
        if len(pcm_frame) != FRAME_SAMPLES * 2:
            return False, rms_db

        vad_hit = bool(self._vad.is_speech(pcm_frame, SAMPLE_RATE))
        if not self.noise_suppression:
            return vad_hit, rms_db

        margin_db = 9.0
        above_floor = rms_db > (self._noise_floor_db + margin_db)
        if not vad_hit or not above_floor:
            # Exponentially track ambient background noise floor
            self._noise_floor_db = 0.92 * self._noise_floor_db + 0.08 * min(rms_db, -28.0)
            return False, rms_db
        return True, rms_db


class AudioPlaybackController:
    """Interruptible audio playback controller supporting instant barge-in."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._is_playing = False

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    def interrupt(self) -> bool:
        """Immediately halt ongoing speech playback."""
        was_playing = self._is_playing
        self._stop_event.set()
        return was_playing

    def play_audio_bytes(
        self,
        audio_bytes: bytes,
        on_progress: Callable[[float], None] | None = None,
    ) -> bool:
        """Play audio bytes synchronously until completion or barge-in interrupt.

        Returns True if playback finished cleanly, False if interrupted.
        """
        samples, sample_rate = decode_audio_bytes_to_float32(audio_bytes)
        if samples.size == 0:
            return True

        with self._lock:
            self._stop_event.clear()
            self._is_playing = True
            channels = 1 if samples.ndim == 1 else samples.shape[1]
            chunk_size = max(512, int(sample_rate * 0.03))
            interrupted = False
            try:
                with sd.OutputStream(
                    samplerate=sample_rate,
                    channels=channels,
                    dtype="float32",
                    blocksize=chunk_size,
                ) as stream:
                    total = len(samples)
                    idx = 0
                    while idx < total:
                        if self._stop_event.is_set():
                            interrupted = True
                            break
                        end = min(total, idx + chunk_size)
                        chunk = samples[idx:end]
                        if chunk.ndim == 1:
                            chunk = chunk.reshape(-1, 1)
                        stream.write(chunk)
                        idx = end
                        if on_progress:
                            on_progress(idx / max(1, total))
            finally:
                self._is_playing = False
        return not interrupted
