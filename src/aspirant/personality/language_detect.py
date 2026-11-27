"""Automatic language & script detection across 18+ Indian languages and Hinglish."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class LanguageProfile:
    code: str
    label: str
    script: str
    is_code_switched: bool
    confidence: float


SUPPORTED_LANGUAGES: dict[str, tuple[str, str]] = {
    "en": ("English", "Latin"),
    "hi": ("Hindi", "Devanagari"),
    "hinglish": ("Hinglish", "Latin/Devanagari Mix"),
    "bho": ("Bhojpuri", "Devanagari"),
    "mag": ("Magahi", "Devanagari"),
    "mai": ("Maithili", "Devanagari"),
    "mr": ("Marathi", "Devanagari"),
    "sa": ("Sanskrit", "Devanagari"),
    "bn": ("Bengali", "Bengali"),
    "as": ("Assamese", "Bengali-Assamese"),
    "pa": ("Punjabi", "Gurmukhi"),
    "gu": ("Gujarati", "Gujarati"),
    "or": ("Odia", "Odia"),
    "ta": ("Tamil", "Tamil"),
    "te": ("Telugu", "Telugu"),
    "kn": ("Kannada", "Kannada"),
    "ml": ("Malayalam", "Malayalam"),
    "ur": ("Urdu", "Perso-Arabic"),
}

_HINGLISH_MARKERS = frozenset(
    {
        "kya", "hai", "hain", "nahi", "nhi", "kaise", "kaisa", "kaisi", "karo",
        "karna", "krna", "batao", "btana", "mera", "meri", "mere", "tum", "aap",
        "bhai", "yaar", "dost", "samjhao", "samajh", "acha", "accha", "theek",
        "thik", "haan", "han", "kyunki", "kyuki", "chahiye", "abhi", "kal",
        "aaj", "mein", "main", "hum", "woh", "yeh", "kuch", "sab", "bahut",
        "bohot", "thoda", "jaldi", "madad", "kaam", "bolo", "sunao", "likho",
        "banao", "chalao", "kholo", "band", "namaste", "shukriya", "dhanyavaad",
    }
)

_DEVANAGARI_HINTS: dict[str, frozenset[str]] = {
    "mr": frozenset({"आहे", "आहेत", "नाही", "तुम्ही", "माझं", "माझे", "कसे", "काय", "करा", "मराठी", "मराठीत"}),
    "bho": frozenset({"बा", "बानी", "बाटे", "रउआ", "हमरा", "काहे", "भोजपुरी", "होई", "कइसन", "चाहीं"}),
    "mag": frozenset({"हई", "हथिन", "मगही", "तोहर", "काहें", "अइसन", "एगो"}),
    "mai": frozenset({"अछि", "छथि", "मैथिली", "अहाँ", "केना", "छै", "अहाँक"}),
    "sa": frozenset({"अस्ति", "भवति", "कथम्", "संस्कृतम्", "नमः", "अहम्", "त्वम्", "पठामि", "पठति"}),
}

_ROMAN_REGIONAL_HINTS: dict[str, frozenset[str]] = {
    "bho": frozenset({"raua", "hamra", "kaisan", "bani", "bhojpuri", "kahe"}),
    "mag": frozenset({"magahi", "hamar", "tohar", "aisan"}),
    "mai": frozenset({"maithili", "ahaan", "achhi"}),
}

_WORD_RE = re.compile(r"[a-zA-Z]+")


def _count_range(text: str, start: int, end: int) -> int:
    return sum(1 for ch in text if start <= ord(ch) <= end)


def detect_language(text: str) -> LanguageProfile:
    """Identify the spoken/written language and script without unnecessary translation."""
    sample = text.strip()
    if not sample:
        return LanguageProfile("en", "English", "Latin", False, 0.5)

    latin_count = sum(1 for ch in sample if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    deva_count = _count_range(sample, 0x0900, 0x097F)
    beng_count = _count_range(sample, 0x0980, 0x09FF)
    guru_count = _count_range(sample, 0x0A00, 0x0A7F)
    guj_count = _count_range(sample, 0x0A80, 0x0AFF)
    odia_count = _count_range(sample, 0x0B00, 0x0B7F)
    tamil_count = _count_range(sample, 0x0B80, 0x0BFF)
    telugu_count = _count_range(sample, 0x0C00, 0x0C7F)
    kannada_count = _count_range(sample, 0x0C80, 0x0CFF)
    mal_count = _count_range(sample, 0x0D00, 0x0D7F)
    arabic_count = _count_range(sample, 0x0600, 0x06FF)

    script_counts = [
        ("deva", deva_count),
        ("beng", beng_count),
        ("guru", guru_count),
        ("guj", guj_count),
        ("odia", odia_count),
        ("tamil", tamil_count),
        ("telugu", telugu_count),
        ("kannada", kannada_count),
        ("mal", mal_count),
        ("arabic", arabic_count),
    ]
    top_script, top_count = max(script_counts, key=lambda item: item[1])

    if top_count >= 2:
        code_switched = latin_count >= 3
        if top_script == "deva":
            tokens = set(re.findall(r"[\u0900-\u097F]+", sample))
            best_lang = None
            best_hits = 0
            for lang_code, markers in _DEVANAGARI_HINTS.items():
                hits = len(tokens & markers)
                if hits > best_hits:
                    best_hits = hits
                    best_lang = lang_code
            if best_lang and best_hits > 0:
                label, script = SUPPORTED_LANGUAGES[best_lang]
                return LanguageProfile(best_lang, label, script, code_switched, 0.88)
            if code_switched:
                return LanguageProfile("hinglish", "Hinglish", "Devanagari + Latin", True, 0.90)
            return LanguageProfile("hi", "Hindi", "Devanagari", False, 0.92)

        if top_script == "beng":
            # Assamese uses 'ৰ' (U+09F0) and 'ৱ' (U+09F1)
            code = "as" if ("\u09F0" in sample or "\u09F1" in sample) else "bn"
            label, script = SUPPORTED_LANGUAGES[code]
            return LanguageProfile(code, label, script, code_switched, 0.92)

        direct_map = {
            "guru": "pa",
            "guj": "gu",
            "odia": "or",
            "tamil": "ta",
            "telugu": "te",
            "kannada": "kn",
            "mal": "ml",
            "arabic": "ur",
        }
        code = direct_map[top_script]
        label, script = SUPPORTED_LANGUAGES[code]
        return LanguageProfile(code, label, script, code_switched, 0.94)

    # Pure or mostly Latin text: check for Bhojpuri/Magahi/Maithili or Hinglish
    words = [w.lower() for w in _WORD_RE.findall(sample)]
    if words:
        word_set = set(words)
        for lang_code, markers in _ROMAN_REGIONAL_HINTS.items():
            if len(word_set & markers) >= 2:
                label, _ = SUPPORTED_LANGUAGES[lang_code]
                return LanguageProfile(lang_code, label, "Latin", True, 0.82)

        hinglish_hits = sum(1 for w in words if w in _HINGLISH_MARKERS)
        if hinglish_hits >= 2 or (len(words) <= 4 and hinglish_hits >= 1 and any(w in {"namaste", "shukriya", "bhai", "yaar", "kaise", "kya"} for w in words)):
            return LanguageProfile("hinglish", "Hinglish", "Latin", True, 0.87)

    return LanguageProfile("en", "English", "Latin", False, 0.90)
