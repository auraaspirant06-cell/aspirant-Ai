"""3D AI Robot state machine synchronizing IDLE, LISTENING, THINKING, SPEAKING, CODING, WORKING, SUCCESS, ERROR."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from enum import Enum
import threading
from typing import Any

from aspirant.core.events import EventBus
from aspirant.robot.animation_controller import ROBOT_STATE_PROFILES, compute_animation_frame


class RobotState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    CODING = "CODING"
    WORKING = "WORKING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


ROBOT_STATES: tuple[str, ...] = tuple(s.value for s in RobotState)

_VOICE_STATE_MAP: dict[str, RobotState] = {
    "idle": RobotState.IDLE,
    "armed_wake_word": RobotState.IDLE,
    "listening": RobotState.LISTENING,
    "transcribing": RobotState.LISTENING,
    "thinking": RobotState.THINKING,
    "speaking": RobotState.SPEAKING,
}


class RobotAvatarController:
    """Thread-safe controller bridging backend tasks/voice and the interactive 3D Robot HUD."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._lock = threading.RLock()
        self.event_bus = event_bus
        self._state: RobotState = RobotState.IDLE
        self._status_text: str = "Standing by — say 'Hey Baby' or ask anything"
        self._speech_amplitude: float = 0.0
        self._wake_phrase: str = "Hey Baby"
        self._voice_gender: str = "female"
        self._history: deque[dict[str, Any]] = deque(maxlen=25)
        self._updated_at: str = datetime.now(timezone.utc).isoformat()

    def set_state(
        self,
        state: RobotState | str,
        status_text: str | None = None,
        speech_amplitude: float = 0.0,
    ) -> dict[str, Any]:
        key = state.value if isinstance(state, RobotState) else str(state).strip().upper()
        try:
            target = RobotState(key)
        except ValueError as exc:
            raise ValueError(f"Unsupported robot state {state!r}. Valid: {ROBOT_STATES}") from exc

        with self._lock:
            self._state = target
            self._speech_amplitude = max(0.0, min(1.0, float(speech_amplitude)))
            profile = ROBOT_STATE_PROFILES[target.value]
            self._status_text = (status_text or profile.status_badge).strip()
            self._updated_at = datetime.now(timezone.utc).isoformat()
            snap = self.snapshot_unlocked()
            self._history.append(
                {
                    "state": target.value,
                    "status_text": self._status_text,
                    "timestamp": self._updated_at,
                }
            )

        if self.event_bus is not None:
            self.event_bus.publish("robot.state", snap)
        return snap

    def sync_from_voice_state(self, voice_state: str, *, amplitude: float = 0.0) -> dict[str, Any]:
        mapped = _VOICE_STATE_MAP.get(voice_state.lower(), RobotState.IDLE)
        return self.set_state(mapped, speech_amplitude=amplitude)

    def update_voice_settings(self, *, wake_phrase: str | None = None, voice_gender: str | None = None) -> None:
        with self._lock:
            if wake_phrase:
                self._wake_phrase = wake_phrase.strip()
            if voice_gender in {"female", "male"}:
                self._voice_gender = voice_gender

    def snapshot_unlocked(self) -> dict[str, Any]:
        frame = compute_animation_frame(self._state.value, phase=0.0, speech_amplitude=self._speech_amplitude)
        return {
            "state": self._state.value,
            "supported_states": list(ROBOT_STATES),
            "status_text": self._status_text,
            "speech_amplitude": self._speech_amplitude,
            "wake_phrase": self._wake_phrase,
            "voice_gender": self._voice_gender,
            "updated_at": self._updated_at,
            "animation": frame,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                **self.snapshot_unlocked(),
                "recent_transitions": list(self._history),
            }
