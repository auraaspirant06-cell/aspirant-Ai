"""Sensitive credential and national-ID redaction before storage or logging."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class RedactionResult:
    text: str
    redacted_count: int
    categories: tuple[str, ...]


_RULES: list[tuple[str, re.Pattern[str], str]] = [
    ("api_key", re.compile(r"\b(?:AIza[0-9A-Za-z\-_]{20,}|sk-[0-9A-Za-z\-_]{20,}|gsk_[0-9A-Za-z\-_]{20,}|hf_[0-9A-Za-z\-_]{20,})\b"), "[REDACTED_API_KEY]"),
    ("aadhaar", re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b"), "[REDACTED_AADHAAR]"),
    ("pan", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[REDACTED_PAN]"),
    ("otp", re.compile(r"(?i)(\b(?:otp|one[\s-]?time[\s-]?password|verification\s*code)\b[^\d\n]{0,16})\b\d{4,8}\b"), r"\1[REDACTED_OTP]"),
    ("secret_kv", re.compile(r"(?i)(\b(?:password|passcode|pin|api[_\s-]?key|secret[_\s-]?key|access[_\s-]?token|bearer)\b\s*[:=]\s*)\S+"), r"\1[REDACTED_SECRET]"),
]


def redact_sensitive_content(text: str) -> RedactionResult:
    """Mask Aadhaar, PAN, OTPs, passwords, and API keys before memory persistence."""
    updated = text
    total_hits = 0
    found_categories: list[str] = []
    for category, pattern, replacement in _RULES:
        updated, count = pattern.subn(replacement, updated)
        if count > 0:
            total_hits += count
            found_categories.append(category)
    return RedactionResult(
        text=updated,
        redacted_count=total_hits,
        categories=tuple(found_categories),
    )


def contains_sensitive_secret(text: str) -> bool:
    """Return True if text contains recognizable national IDs, OTPs, or keys."""
    return redact_sensitive_content(text).redacted_count > 0
