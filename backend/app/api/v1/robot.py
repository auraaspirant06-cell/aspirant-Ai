"""3D AI Robot synchronization API routes for the Next.js Ecosystem Web Console."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aspirant.robot.animation_controller import ROBOT_STATE_PROFILES, compute_animation_frame
from aspirant.robot.avatar_controller import ROBOT_STATES

router = APIRouter(prefix="/robot", tags=["3D AI Robot Interface"])

RobotStateName = Literal[
    "IDLE",
    "LISTENING",
    "THINKING",
    "SPEAKING",
    "CODING",
    "WORKING",
    "SUCCESS",
    "ERROR",
]

_ECOSYSTEM_ROBOT_STATE: dict = {
    "state": "IDLE",
    "status_text": "Standing by — say 'Hey Baby' or ask a question",
    "speech_amplitude": 0.0,
    "wake_phrase": "Hey Baby",
    "voice_gender": "female",
    "updated_at": datetime.now(timezone.utc).isoformat(),
}


class RobotStateUpdateRequest(BaseModel):
    state: RobotStateName
    status_text: str = Field(default="", max_length=160)
    speech_amplitude: float = Field(default=0.0, ge=0.0, le=1.0)
    wake_phrase: str | None = Field(default=None, max_length=60)
    voice_gender: Literal["female", "male"] | None = None


@router.get("/state")
async def get_robot_state() -> dict:
    """Return current 3D Robot state, animation profile, and supported state list."""
    state = _ECOSYSTEM_ROBOT_STATE["state"]
    frame = compute_animation_frame(
        state, phase=0.0, speech_amplitude=_ECOSYSTEM_ROBOT_STATE["speech_amplitude"]
    )
    return {
        **_ECOSYSTEM_ROBOT_STATE,
        "supported_states": list(ROBOT_STATES),
        "animation": frame,
    }


@router.post("/state")
async def update_robot_state(body: RobotStateUpdateRequest) -> dict:
    """Transition the interactive 3D Robot animation state with TTS mouth amplitude."""
    profile = ROBOT_STATE_PROFILES[body.state]
    _ECOSYSTEM_ROBOT_STATE["state"] = body.state
    _ECOSYSTEM_ROBOT_STATE["status_text"] = (body.status_text or profile.status_badge).strip()
    _ECOSYSTEM_ROBOT_STATE["speech_amplitude"] = body.speech_amplitude
    if body.wake_phrase is not None and body.wake_phrase.strip():
        _ECOSYSTEM_ROBOT_STATE["wake_phrase"] = body.wake_phrase.strip()
    if body.voice_gender is not None:
        _ECOSYSTEM_ROBOT_STATE["voice_gender"] = body.voice_gender
    _ECOSYSTEM_ROBOT_STATE["updated_at"] = datetime.now(timezone.utc).isoformat()
    return await get_robot_state()
