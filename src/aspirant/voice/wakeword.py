"""Wake-word detection ('Hey Baby', 'Hey Aspirant', 'Aspirant', 'Hello Aspirant') and voice confirmations."""

from __future__ import annotations

import re

from aspirant.personality.system_prompt import OWNER_NAMES, detect_interaction_mode

DEFAULT_WAKE_WORD = "Hey Baby"
WAKE_WORD_PHRASES = ("Hey Baby", "Hey Aspirant", "Aspirant", "Hello Aspirant", "Hey Nova")

_WAKE_PATTERNS = [
    re.compile(r"(?i)\b(?:hey|hi|hello|ok|okay|oye|sun|suno)\s+baby\b"),
    re.compile(r"(?i)^\s*baby\b(?:[,\s:?!-]+|$)"),
    re.compile(r"हे\s*बेबी|हाय\s*बेबी|सुनो\s*बेबी"),
    re.compile(r"(?i)\b(?:hey|hi|hello|ok|okay|oye|sun|suno)\s+aspirant\b"),
    re.compile(r"(?i)^\s*aspirant\b(?:[,\s:?!-]+|$)"),
    re.compile(r"(?i)\b(?:hey|hi|hello)\s+(?:espirant|asprint|aspirants|aspeerant)\b"),
    re.compile(r"(?i)\b(?:hey|hi|hello|ok|okay)\s+nova\b"),
    re.compile(r"हे\s*एस्पिरेंट|हाय\s*एस्पिरेंट|सुनो\s*एस्पिरेंट|एस्पिरेंट"),
]


def match_wake_word(transcript: str, wake_phrase: str = DEFAULT_WAKE_WORD) -> tuple[bool, str]:
    """Detect configurable wake phrase ('Hey Baby', 'Hey Aspirant', etc.) and return (matched, trailing_command)."""
    cleaned = transcript.strip()
    if not cleaned:
        return False, ""

    norm_custom = re.escape(wake_phrase.strip().replace("_", " "))
    custom_re = re.compile(rf"(?i)\b{norm_custom}\b")
    for pattern in [custom_re, *_WAKE_PATTERNS]:
        match = pattern.search(cleaned)
        if match:
            trailing = (cleaned[: match.start()] + " " + cleaned[match.end() :]).strip(" ,.?!;:-")
            return True, trailing

    return False, cleaned


def build_voice_confirmation(command_text: str, owner_title: str = "Boss") -> str:
    """Return brief step-4 voice confirmation before execution (addressing owner as Harsh or Boss)."""
    cleaned = command_text.strip()
    if not cleaned or cleaned.lower() in {"hey baby", "baby", "hello baby", "hey aspirant", "hello aspirant"}:
        return "Yes, I'm listening. Tell me."

    owner = owner_title if owner_title in OWNER_NAMES else "Boss"
    lowered = cleaned.lower()
    if "deploy" in lowered or "deployment" in lowered:
        return f"Understood {owner}. Preparing deployment steps."
    if "fastapi" in lowered:
        return f"Sure {owner}. Generating FastAPI production-ready project now."
    mode = detect_interaction_mode(cleaned)
    if mode == "project_generator":
        return f"Sure {owner}. Generating complete production-ready project now."
    if mode == "debugging":
        return f"On it {owner}. Analyzing the error details now."
    if mode == "learning":
        return f"Sure {owner}. Explaining step-by-step with clear examples."
    if mode == "coding":
        return f"Sure {owner}. Generating clean production code now."
    return f"Sure {owner}. Working on that now."
