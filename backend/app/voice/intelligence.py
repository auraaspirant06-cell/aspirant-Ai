"""Continuous multilingual voice intelligence across 13 Indian/global languages and guarded command execution."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any


LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "hinglish": "Hinglish",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "kn": "Kannada",
    "ml": "Malayalam",
    "ur": "Urdu",
    "or": "Odia",
    "as": "Assamese",
}

SAME_LANGUAGE_GREETINGS: dict[str, str] = {
    "en": "Understood",
    "hi": "जी बिल्कुल",
    "hinglish": "Haan bilkul",
    "bn": "নিশ্চয়ই",
    "ta": "சரி",
    "te": "సరే",
    "mr": "हो नक्कीच",
    "gu": "ચોક્કસ",
    "pa": "ਜੀ ਬਿਲਕੁਲ",
    "kn": "ಖಂಡಿತ",
    "ml": "തീർച്ചയായும்",
    "ur": "جی بالکل",
    "or": "ନିଶ୍ଚିତ ଭାବରେ",
    "as": "নিশ্চয়",
}

HINGLISH_MARKERS = frozenset({
    "bhai", "yaar", "kya", "kaise", "kaisa", "aaj", "kal", "mujhe", "mera", "meri",
    "batao", "karo", "karna", "chahiye", "hai", "hain", "haan", "nahi", "samjhao",
    "kholo", "dikhao", "plz", "theek",
})


def detect_voice_language(text: str) -> tuple[str, str]:
    """Detect user language across English and 12 major Indian languages accurately."""
    cleaned = text.strip()
    if not cleaned:
        return "en", "English"

    # Script-specific fast path before Devanagari disambiguation
    for ch in cleaned:
        code = ord(ch)
        if 0x0B80 <= code <= 0x0BFF:
            return "ta", LANGUAGE_NAMES["ta"]
        if 0x0C00 <= code <= 0x0C7F:
            return "te", LANGUAGE_NAMES["te"]
        if 0x0C80 <= code <= 0x0CFF:
            return "kn", LANGUAGE_NAMES["kn"]
        if 0x0D00 <= code <= 0x0D7F:
            return "ml", LANGUAGE_NAMES["ml"]
        if 0x0A80 <= code <= 0x0AFF:
            return "gu", LANGUAGE_NAMES["gu"]
        if 0x0A00 <= code <= 0x0A7F:
            return "pa", LANGUAGE_NAMES["pa"]
        if 0x0B00 <= code <= 0x0B7F:
            return "or", LANGUAGE_NAMES["or"]
        if 0x0600 <= code <= 0x06FF:
            return "ur", LANGUAGE_NAMES["ur"]

    # Bengali vs Assamese (Assamese uses ৰ U+09F0 and ৱ U+09F1 + distinct pronouns)
    if any(0x0980 <= ord(ch) <= 0x09FF for ch in cleaned):
        if "\u09f0" in cleaned or "\u09f1" in cleaned or "মই" in cleaned or "অসমীয়া" in cleaned:
            return "as", LANGUAGE_NAMES["as"]
        return "bn", LANGUAGE_NAMES["bn"]

    # Devanagari: Marathi vs Hindi
    if any(0x0900 <= ord(ch) <= 0x097F for ch in cleaned):
        marathi_markers = ("आहात", "मला", "मराठी", "सांगा", "माझे", "तुम्ही", "कसे", "आहे")
        if any(m in cleaned for m in marathi_markers):
            return "mr", LANGUAGE_NAMES["mr"]
        return "hi", LANGUAGE_NAMES["hi"]

    # Hinglish code-switched Latin heuristic before English fallback
    tokens = {tok for tok in re.findall(r"[a-zA-Z]+", cleaned.lower())}
    if len(tokens & HINGLISH_MARKERS) >= 2:
        return "hinglish", LANGUAGE_NAMES["hinglish"]

    try:
        from aspirant.personality.language import detect_language

        detected = detect_language(cleaned)
        lang_code = getattr(detected, "language", "en")
        if lang_code in LANGUAGE_NAMES:
            return lang_code, LANGUAGE_NAMES[lang_code]
    except Exception:
        pass

    return "en", LANGUAGE_NAMES["en"]


@dataclass(slots=True)
class VoiceConfidenceResult:
    confidence: float
    far_field_detected: bool
    noise_filtered_snr_db: float
    should_interrupt_tts: bool


def evaluate_voice_signal(
    *,
    transcript: str,
    signal_db: float = -18.0,
    noise_db: float = -42.0,
    far_field: bool = False,
    barge_in: bool = False,
) -> VoiceConfidenceResult:
    """Compute acoustic + lexical voice confidence and noise-filtered SNR."""
    snr = signal_db - noise_db
    if far_field:
        snr += 4.5  # Beamforming gain model
    snr_score = max(0.0, min(1.0, snr / 35.0))
    lexical_score = min(1.0, max(0.25, len(transcript.strip()) / 18.0)) if transcript.strip() else 0.0
    confidence = round(0.55 * snr_score + 0.45 * lexical_score, 4)
    return VoiceConfidenceResult(
        confidence=confidence,
        far_field_detected=far_field or snr < 16.0,
        noise_filtered_snr_db=round(snr, 2),
        should_interrupt_tts=barge_in,
    )


@dataclass(slots=True)
class VoiceCommandIntent:
    intent: str
    action_target: str
    sensitive: bool
    requires_authorization: bool
    authorized: bool
    parameters: dict[str, Any] = field(default_factory=dict)


class VoiceCommandRouter:
    """Routes natural language commands to desktop/productivity/AI intents with authorization gates."""

    SENSITIVE_KEYWORDS = (
        "delete",
        "remove",
        "format",
        "transfer",
        "payment",
        "shutdown",
        "publish",
        "password",
        "disable security",
        "हटाओ",
        "डिलीट",
    )

    def classify_and_authorize(
        self,
        *,
        transcript: str,
        explicit_authorization: bool = False,
        speaker_access_level: str = "trusted",
    ) -> VoiceCommandIntent:
        lowered = transcript.lower().strip()
        is_sensitive = any(k in lowered for k in self.SENSITIVE_KEYWORDS)

        if any(k in lowered for k in ("open app", "launch", "start ", "खोलो", "ऐप")):
            intent = "open_app"
        elif any(k in lowered for k in ("search file", "find file", "locate", "फाइल")):
            intent = "search_files"
        elif any(k in lowered for k in ("open browser", "website", "url", "ब्राउज़र", "search web")):
            intent = "open_browser"
        elif any(k in lowered for k in ("task", "todo", "reminder", "habit", "प्लान", "रिमाइंडर")):
            intent = "manage_tasks"
        elif any(k in lowered for k in ("note", "calendar", "email", "schedule", "summary")):
            intent = "productivity"
        else:
            intent = "ai_assistant"

        if speaker_access_level != "trusted" and intent in {"open_app", "search_files", "manage_tasks"}:
            is_sensitive = True

        requires_auth = is_sensitive
        authorized = (not requires_auth) or (explicit_authorization and speaker_access_level == "trusted")

        return VoiceCommandIntent(
            intent=intent,
            action_target=transcript.strip()[:160],
            sensitive=is_sensitive,
            requires_authorization=requires_auth,
            authorized=authorized,
            parameters={"speaker_access_level": speaker_access_level},
        )
