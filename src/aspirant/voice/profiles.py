"""Female & Male voice catalog, Indian language voice routing, wake phrase config, and prosody presets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VoiceConfig:
    """User-configurable voice & wake-word parameters."""

    tts_provider: str = "auto"          # auto (Gemini 3.8 TTS -> edge-tts -> sapi5) | gemini | edge-tts | sapi5
    stt_provider: str = "auto"          # auto | gemini | openai | groq | faster-whisper
    voice_gender: str = "female"        # female | male
    wake_phrase: str = "Hey Baby"       # Configurable default wake phrase
    wake_word_enabled: bool = True
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

MALE_NEURAL_VOICES: dict[str, str] = {
    "en": "en-IN-PrabhatNeural",
    "hi": "hi-IN-MadhurNeural",
    "hinglish": "hi-IN-MadhurNeural",
    "bho": "hi-IN-MadhurNeural",
    "mag": "hi-IN-MadhurNeural",
    "mai": "hi-IN-MadhurNeural",
    "sa": "hi-IN-MadhurNeural",
    "mr": "mr-IN-ManoharNeural",
    "bn": "bn-IN-BashkarNeural",
    "as": "bn-IN-BashkarNeural",
    "gu": "gu-IN-NiranjanNeural",
    "ta": "ta-IN-ValluvarNeural",
    "te": "te-IN-MohanNeural",
    "kn": "kn-IN-GaganNeural",
    "ml": "ml-IN-MidhunNeural",
    "ur": "ur-IN-SalmanNeural",
    "pa": "hi-IN-MadhurNeural",
    "or": "hi-IN-MadhurNeural",
}

GEMINI_FEMALE_VOICES = ("Kore", "Aoede", "Leda", "Zephyr", "Sulafat", "Vindemiatrix")
GEMINI_MALE_VOICES = ("Puck", "Charon", "Fenrir", "Orus", "Iapetus", "Umbriel")

EMOTION_STYLE_PROMPTS: dict[str, str] = {
    "neutral": "clear, natural, composed voice",
    "friendly": "warm, natural, friendly voice",
    "cheerful": "cheerful, bright, encouraging voice",
    "calm": "calm, soothing, patient voice",
    "professional": "articulate, confident, professional voice",
    "empathetic": "gentle, calm, empathetic and helpful voice",
}


def resolve_edge_voice(
    language_code: str, gender: str = "female", override: str = "auto"
) -> str:
    """Resolve an Indian neural voice by language code and preferred gender."""
    if override and override != "auto":
        return override
    if gender.strip().lower() == "male":
        return MALE_NEURAL_VOICES.get(language_code, "en-IN-PrabhatNeural")
    return FEMALE_NEURAL_VOICES.get(language_code, "en-IN-NeerjaNeural")


def resolve_edge_female_voice(language_code: str, override: str = "auto") -> str:
    """Backwards-compatible female neural voice resolver."""
    return resolve_edge_voice(language_code, gender="female", override=override)


def resolve_gemini_voice(gender: str = "female", override: str = "auto") -> str:
    """Resolve a prebuilt Gemini 3.8 TTS voice name by gender or override."""
    if override and override not in ("auto", ""):
        return override
    if gender.strip().lower() == "male":
        return GEMINI_MALE_VOICES[0]
    return GEMINI_FEMALE_VOICES[0]


def format_edge_prosody(speed: float, pitch_hz: int) -> tuple[str, str]:
    """Convert numeric speed/pitch into edge-tts rate and pitch strings."""
    bounded_speed = max(0.75, min(1.50, speed))
    rate_pct = int(round((bounded_speed - 1.0) * 100))
    rate_str = f"{rate_pct:+d}%"

    bounded_pitch = max(-20, min(20, int(pitch_hz)))
    pitch_str = f"{bounded_pitch:+d}Hz"
    return rate_str, pitch_str
