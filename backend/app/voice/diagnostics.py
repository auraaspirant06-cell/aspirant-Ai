"""Automatic microphone testing, audio device diagnostics, and actionable repair guidance."""

from __future__ import annotations

import math
from typing import Any


def diagnose_audio_devices(test_samples: list[float] | None = None) -> dict[str, Any]:
    """Inspect available audio input/output devices and optionally test live mic frame levels."""
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    issues: list[str] = []
    guidance: list[str] = []

    try:
        import sounddevice as sd

        raw_devices = sd.query_devices()
        for idx, dev in enumerate(raw_devices):
            entry = {
                "index": idx,
                "name": str(dev.get("name", f"Device {idx}")),
                "default_samplerate": int(dev.get("default_samplerate", 16000)),
            }
            if int(dev.get("max_input_channels", 0)) > 0:
                inputs.append(entry)
            if int(dev.get("max_output_channels", 0)) > 0:
                outputs.append(entry)
    except Exception as exc:
        issues.append(f"Audio subsystem probe unavailable: {exc}")
        guidance.append("Verify Windows Audio service (`Audiosrv`) and microphone driver installation.")

    if not inputs:
        issues.append("No active microphone input devices detected.")
        guidance.append(
            "Enable Microphone access under Windows Settings -> Privacy & security -> Microphone, and plug in or unmute your mic."
        )
    if not outputs:
        issues.append("No speaker or audio output devices detected.")
        guidance.append("Verify default playback device in Windows Sound settings.")

    rms_level: float | None = None
    if test_samples:
        rms_level = round(
            math.sqrt(sum(float(x) * float(x) for x in test_samples) / len(test_samples)),
            6,
        )
        if rms_level < 0.005:
            issues.append("Captured microphone level is near zero (possible mute or wrong input gain).")
            guidance.append("Increase Windows microphone input volume above 65% and verify hardware mute switch.")
        elif rms_level > 0.96:
            issues.append("Microphone signal clipping detected.")
            guidance.append("Reduce mic boost or speak further from the microphone.")

    if not issues:
        guidance.append("Microphone and output devices look healthy for continuous listening.")

    return {
        "mic_available": bool(inputs),
        "input_devices": inputs[:8],
        "output_devices": outputs[:8],
        "rms_level": rms_level,
        "health_status": "healthy" if not issues else "attention_needed",
        "issues_detected": issues,
        "repair_guidance": guidance,
    }
