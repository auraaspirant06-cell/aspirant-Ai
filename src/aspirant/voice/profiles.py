"""Female voice catalog, Indian language voice routing, and prosody presets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VoiceConfig:
    """User-configurable female voice parameters."""

    tts_provider: str = "auto"          # auto (Gemini 3.8 TTS -> edge-tts -> sapi5) | gemini | edge-tts | sapi5
    stt_provider: str = "auto"          # auto | gemini | openai | groq | faster-whisper
    speed: float = 1.0                  # 0.75 .. 1.50
    pitch_hz: int = 0                   # -20 .. +20
    emotion: str = "friendly"           # neutral | friendly | calm | professional | cheerful | empathetic
    noise_suppression: bool = True
    activation_mode: str = "idle"       # idle | push_to_talk | wake_word | hands_free
    voice_override: str = "auto"        # auto or explicit voice name


FEMALE_NEURAL_VOICES: dict[str, str] = {
    "en": "en-IN-NeerjaNeural",
    "hi": "hi-IN-SwaraNeural",
    "hinglish": "hi-IN-SwaraNeural",
    "bho": "hi-IN-SwaraNeural",
    "mag": "hi-IN-SwaraNeural",
    "mai": "hi-IN-SwaraNeural",
    "sa": "hi-IN-SwaraNeural",
    "mr": "mr-IN-AarohiNeural",
    "bn": "bn-IN-TanishaaNeural",
    "as": "bn-IN-TanishaaNeural",
    "gu": "gu-IN-DhwaniNeural",
    "ta": "ta-IN-PallaviNeural",
    "te": "te-IN-ShrutiNeural",
    "kn": "kn-IN-SapnaNeural",
    "ml": "ml-IN-SobhanaNeural",
    "ur": "ur-IN-GulNeural",
    "pa": "hi-IN-SwaraNeural",
    "or": "hi-IN-SwaraNeural",
}

GEMINI_FEMALE_VOICES = ("Kore", "Aoede", "Leda", "Zephyr")

EMOTION_STYLE_PROMPTS: dict[str, str] = {
    "neutral": "clear, natural, composed female voice",
    "friendly": "warm, natural, friendly female voice",
    "cheerful": "cheerful, bright, encouraging female voice",
    "calm": "calm, soothing, patient female voice",
    "professional": "articulate, confident, professional female voice",
    "empathetic": "gentle, calm, empathetic and helpful female voice",
}


def resolve_edge_female_voice(language_code: str, override: str = "auto") -> str:
    if override and override != "auto":
        return override
    return FEMALE_NEURAL_VOICES.get(language_code, "en-IN-NeerjaNeural")


def format_edge_prosody(speed: float, pitch_hz: int) -> tuple[str, str]:
    """Convert numeric speed/pitch into edge-tts rate and pitch strings."""
    bounded_speed = max(0.75, min(1.50, speed))
    rate_pct = int(round((bounded_speed - 1.0) * 100))
    rate_str = f"{rate_pct:+d}%"

    bounded_pitch = max(-20, min(20, int(pitch_hz)))
    pitch_str = f"{bounded_pitch:+d}Hz"
    return rate_str, pitch_str
