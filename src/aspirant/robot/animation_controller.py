"""Animation choreography profiles and speech-synchronized mouth kinematics for the 3D AI robot."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any


@dataclass(frozen=True, slots=True)
class RobotAnimationProfile:
    state: str
    accent_hex: str
    glow_hex: str
    eye_mode: str         # calm | focused | pulsing | expressive | code_visor | happy_arc | alert
    ring_speed: float
    head_bob_amp: float
    wave_bars_active: bool
    status_badge: str


ROBOT_STATE_PROFILES: dict[str, RobotAnimationProfile] = {
    "IDLE": RobotAnimationProfile(
        state="IDLE",
        accent_hex="#38BDF8",
        glow_hex="#7C3AED",
        eye_mode="calm",
        ring_speed=0.6,
        head_bob_amp=0.05,
        wave_bars_active=False,
        status_badge="Ready • Standing By",
    ),
    "LISTENING": RobotAnimationProfile(
        state="LISTENING",
        accent_hex="#22D3EE",
        glow_hex="#0EA5E9",
        eye_mode="focused",
        ring_speed=2.4,
        head_bob_amp=0.03,
        wave_bars_active=True,
        status_badge="Listening • Sound-Wave Active",
    ),
    "THINKING": RobotAnimationProfile(
        state="THINKING",
        accent_hex="#A855F7",
        glow_hex="#6366F1",
        eye_mode="pulsing",
        ring_speed=3.2,
        head_bob_amp=0.07,
        wave_bars_active=False,
        status_badge="Thinking • Reasoning Core",
    ),
    "SPEAKING": RobotAnimationProfile(
        state="SPEAKING",
        accent_hex="#38BDF8",
        glow_hex="#A855F7",
        eye_mode="expressive",
        ring_speed=1.8,
        head_bob_amp=0.08,
        wave_bars_active=True,
        status_badge="Speaking • Lip-Sync Active",
    ),
    "CODING": RobotAnimationProfile(
        state="CODING",
        accent_hex="#06B6D4",
        glow_hex="#3B82F6",
        eye_mode="code_visor",
        ring_speed=2.1,
        head_bob_amp=0.04,
        wave_bars_active=False,
        status_badge="Coding • Architecting Build",
    ),
    "WORKING": RobotAnimationProfile(
        state="WORKING",
        accent_hex="#818CF8",
        glow_hex="#22D3EE",
        eye_mode="pulsing",
        ring_speed=2.6,
        head_bob_amp=0.05,
        wave_bars_active=False,
        status_badge="Working • Executing Task",
    ),
    "SUCCESS": RobotAnimationProfile(
        state="SUCCESS",
        accent_hex="#34D399",
        glow_hex="#22D3EE",
        eye_mode="happy_arc",
        ring_speed=1.2,
        head_bob_amp=0.09,
        wave_bars_active=False,
        status_badge="Success • Verified Complete",
    ),
    "ERROR": RobotAnimationProfile(
        state="ERROR",
        accent_hex="#F43F5E",
        glow_hex="#FB7185",
        eye_mode="alert",
        ring_speed=0.4,
        head_bob_amp=0.01,
        wave_bars_active=False,
        status_badge="Error • Needs Attention",
    ),
}


def compute_animation_frame(
    state: str,
    phase: float,
    speech_amplitude: float = 0.0,
) -> dict[str, Any]:
    """Compute instantaneous 3D kinematics (head tilt, blink, breathing, mouth openness) for UI renderers."""
    normalized = state.strip().upper()
    profile = ROBOT_STATE_PROFILES.get(normalized, ROBOT_STATE_PROFILES["IDLE"])

    blink = 1.0
    # Smooth natural eye blink window every ~2*pi cycle
    cycle = phase % 6.2831853
    if 5.85 <= cycle <= 6.18 and profile.eye_mode not in {"code_visor", "alert"}:
        blink = max(0.08, abs(math.cos((cycle - 5.85) * 9.5)))

    breathing_y = math.sin(phase * 1.4) * profile.head_bob_amp
    head_yaw = math.sin(phase * 0.7) * (0.14 if profile.state in {"IDLE", "LISTENING"} else 0.08)

    clamped_amp = max(0.0, min(1.0, float(speech_amplitude)))
    if profile.state == "SPEAKING":
        base_mouth = 0.25 + 0.55 * abs(math.sin(phase * 4.5))
        mouth_open = min(1.0, max(clamped_amp, base_mouth))
    else:
        mouth_open = 0.06

    return {
        **asdict(profile),
        "blink_open": round(blink, 3),
        "breathing_y": round(breathing_y, 4),
        "head_yaw": round(head_yaw, 4),
        "mouth_open": round(mouth_open, 3),
    }
