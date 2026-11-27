"""Neural voice personalities, preview generator, and owner-consented voice cloning hooks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import PasswordService
from backend.app.infrastructure.db.models import UserModel
from backend.app.voice.speaker_id import extract_voiceprint


@dataclass(frozen=True, slots=True)
class VoicePersonalityPreset:
    id: str
    name: str
    accent: str
    style: str
    voice_id: str
    pitch_rate: float
    speaking_rate: float
    gender: str = "female"


VOICE_PRESETS: tuple[VoicePersonalityPreset, ...] = (
    VoicePersonalityPreset(
        id="aanya-warm",
        name="Aanya — Warm Companion",
        accent="en-IN / hi-IN Natural Indian",
        style="warm-empathetic",
        voice_id="en-IN-NeerjaExpressiveNeural",
        pitch_rate=1.02,
        speaking_rate=1.0,
        gender="female",
    ),
    VoicePersonalityPreset(
        id="kavya-executive",
        name="Kavya — Crisp Executive",
        accent="en-IN Studio Clarity",
        style="concise-executive",
        voice_id="en-IN-KavyaNeural",
        pitch_rate=1.0,
        speaking_rate=1.05,
        gender="female",
    ),
    VoicePersonalityPreset(
        id="meera-mentor",
        name="Meera — Calm Hindi Mentor",
        accent="hi-IN Natural Devanagari",
        style="calm-mentor",
        voice_id="hi-IN-SwaraNeural",
        pitch_rate=0.98,
        speaking_rate=0.96,
        gender="female",
    ),
    VoicePersonalityPreset(
        id="riya-hinglish",
        name="Riya — Expressive Hinglish",
        accent="hi-IN / en-IN Code-Switch",
        style="friendly-hinglish",
        voice_id="hi-IN-AnanyaNeural",
        pitch_rate=1.04,
        speaking_rate=1.02,
        gender="female",
    ),
    VoicePersonalityPreset(
        id="arjun-calm",
        name="Arjun — Confident Male Tech Lead",
        accent="en-IN Studio Male",
        style="confident-executive",
        voice_id="en-IN-PrabhatNeural",
        pitch_rate=1.0,
        speaking_rate=1.0,
        gender="male",
    ),
    VoicePersonalityPreset(
        id="kabir-warm",
        name="Kabir — Warm Hindi/Hinglish Male",
        accent="hi-IN / en-IN Male Companion",
        style="warm-helpful",
        voice_id="hi-IN-MadhurNeural",
        pitch_rate=0.99,
        speaking_rate=1.0,
        gender="male",
    ),
)


def list_voice_presets() -> list[dict[str, Any]]:
    return [asdict(p) for p in VOICE_PRESETS]


def build_voice_preview(preset_id: str, sample_text: str | None = None) -> dict[str, Any]:
    preset = next((p for p in VOICE_PRESETS if p.id == preset_id), VOICE_PRESETS[0])
    phrase = (
        sample_text.strip()
        if sample_text and sample_text.strip()
        else f"Namaste! Main {preset.name.split('—')[0].strip()} hoon, aapki Aspirant AI companion."
    )
    return {
        "preset": asdict(preset),
        "preview_text": phrase,
        "provider_priority": ["gemini-3.8-flash-tts", "edge-tts", "windows-sapi5"],
        "ready": True,
    }


class VoiceCloneHookService:
    """Architecture hook for registering custom voice cloning profiles with owner password + consent."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register_clone_hook(
        self,
        *,
        user_id: str,
        password: str,
        explicit_consent: bool,
        voice_name: str,
        reference_samples: list[float],
    ) -> dict[str, Any]:
        if not explicit_consent:
            raise PermissionError("Voice cloning hook requires explicit written owner consent.")
        user = await self._session.get(UserModel, user_id)
        if not user or not PasswordService.verify_password(password, user.password_hash):
            raise PermissionError("Valid account password is required to register a voice clone hook.")

        sig = extract_voiceprint(reference_samples, voice_name)
        prefs = dict(user.preferences_json or {})
        prefs["voice_clone_hook"] = {
            "voice_name": voice_name.strip() or "Owner Custom Clone",
            "consent_recorded": True,
            "signature_preview": sig[:4],
            "provider_target": "gemini-voice-design-hook",
        }
        user.preferences_json = prefs
        await self._session.flush()
        return {"registered": True, "hook": prefs["voice_clone_hook"]}
