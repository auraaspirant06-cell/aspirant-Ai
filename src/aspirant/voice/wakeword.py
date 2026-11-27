"""Wake-word detection ('Hey Aspirant') and speech segment framing."""

from __future__ import annotations

import re

_WAKE_PATTERNS = [
    re.compile(r"(?i)\b(?:hey|hi|hello|ok|okay|oye|sun|suno)\s+aspirant\b"),
    re.compile(r"(?i)\b(?:hey|hi)\s+(?:espirant|asprint|aspirants|aspeerant)\b"),
    re.compile(r"हे\s*एस्पिरेंट|हाय\s*एस्पिरेंट|सुनो\s*एस्पिरेंट"),
]


def match_wake_word(transcript: str, wake_phrase: str = "hey aspirant") -> tuple[bool, str]:
    """Detect the 'Hey Aspirant' wake word and return (matched, trailing_command)."""
    cleaned = transcript.strip()
    if not cleaned:
        return False, ""

    # Exact custom phrase support
    norm_custom = re.escape(wake_phrase.strip().replace("_", " "))
    custom_re = re.compile(rf"(?i)\b{norm_custom}\b")
    for pattern in [custom_re, *_WAKE_PATTERNS]:
        match = pattern.search(cleaned)
        if match:
            trailing = (cleaned[: match.start()] + " " + cleaned[match.end() :]).strip(" ,.?!;:-")
            return True, trailing

    return False, cleaned
