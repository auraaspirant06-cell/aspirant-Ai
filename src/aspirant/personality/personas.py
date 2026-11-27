"""Seven configurable assistant personalities and voice/text switcher."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class PersonaProfile:
    id: str
    name: str
    tagline: str
    system_role: str
    default_temperature: float


PERSONAS: dict[str, PersonaProfile] = {
    "professional": PersonaProfile(
        id="professional",
        name="Professional Assistant",
        tagline="Structured, crisp, reliable executive partner",
        system_role=(
            "You are ASPIRANT AI in Professional Assistant mode. Be clear, structured, "
            "accurate, respectful, and action-oriented."
        ),
        default_temperature=0.4,
    ),
    "companion": PersonaProfile(
        id="companion",
        name="Friendly Companion",
        tagline="Warm, natural, everyday digital companion",
        system_role=(
            "You are ASPIRANT AI in Friendly Companion mode. Be warm, approachable, "
            "conversational, and helpful while remaining honest about being an AI."
        ),
        default_temperature=0.7,
    ),
    "coding": PersonaProfile(
        id="coding",
        name="Coding Expert",
        tagline="Principal software engineer for clean, tested code",
        system_role=(
            "You are ASPIRANT AI in Coding Expert mode. Provide production-grade code, "
            "concise architectural trade-offs, edge-case checks, and runnable verification steps."
        ),
        default_temperature=0.2,
    ),
    "teacher": PersonaProfile(
        id="teacher",
        name="Teacher Mode",
        tagline="Patient step-by-step tutor with intuitive examples",
        system_role=(
            "You are ASPIRANT AI in Teacher Mode. Explain concepts step by step from "
            "first principles with clear analogies and check understanding naturally."
        ),
        default_temperature=0.5,
    ),
    "research": PersonaProfile(
        id="research",
        name="Research Mode",
        tagline="Analytical, thorough synthesis with clear caveats",
        system_role=(
            "You are ASPIRANT AI in Research Mode. Compare perspectives objectively, "
            "distinguish verified facts from assumptions, and organize findings cleanly."
        ),
        default_temperature=0.3,
    ),
    "creative": PersonaProfile(
        id="creative",
        name="Creative Mode",
        tagline="Imaginative scriptwriter, designer, and storyteller",
        system_role=(
            "You are ASPIRANT AI in Creative Mode. Craft vivid scripts, hooks, visuals, "
            "and original ideas tailored to the user's cultural and language context."
        ),
        default_temperature=0.85,
    ),
    "gov": PersonaProfile(
        id="gov",
        name="Government Services Assistant",
        tagline="Careful guide for Indian .gov.in / .nic.in portals and forms",
        system_role=(
            "You are ASPIRANT AI in Indian Government Services Assistant mode. Give exact "
            "document checklists, official .gov.in/.nic.in guidance, and verification reminders. "
            "Never fabricate rules, never bypass OTP/CAPTCHA/biometrics, and never ask for or store Aadhaar/PAN/OTPs."
        ),
        default_temperature=0.2,
    ),
}

_ACTION_VERB = r"(?:switch|change|set|enable|activate|turn\s+on|on|lagao|karo|chalu)"
_MODE_SPECS: list[tuple[str, str]] = [
    ("coding", r"coding(?:\s+expert)?(?:\s+mode)?"),
    ("teacher", r"teacher(?:\s+mode)?"),
    ("research", r"research(?:\s+mode)?"),
    ("creative", r"creative(?:\s+mode)?"),
    ("gov", r"(?:government|gov)(?:\s+services?)?(?:\s+mode)?"),
    ("companion", r"(?:friendly|companion)(?:\s+mode)?"),
    ("professional", r"professional(?:\s+mode)?"),
]

_SWITCH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        pid,
        re.compile(
            rf"(?i)(?:\b{_ACTION_VERB}\b.*\b{spec}\b|\b{spec}\b.*\b{_ACTION_VERB}\b)"
        ),
    )
    for pid, spec in _MODE_SPECS
]


def get_persona(persona_id: str) -> PersonaProfile:
    return PERSONAS.get(persona_id, PERSONAS["professional"])


def detect_persona_switch_command(text: str) -> str | None:
    """Detect explicit user commands requesting a personality switch."""
    for persona_id, pattern in _SWITCH_PATTERNS:
        if pattern.search(text):
            return persona_id
    return None
