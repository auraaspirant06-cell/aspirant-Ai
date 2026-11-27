"""Phase 2 tests for 18+ Indian language detection, Hinglish, personas, style adaptation, and redaction."""

from __future__ import annotations

import pytest

from aspirant.personality.language_detect import detect_language
from aspirant.personality.personas import PERSONAS, detect_persona_switch_command, get_persona
from aspirant.personality.style_adapter import analyze_style, build_system_instruction
from aspirant.security.redactor import contains_sensitive_secret, redact_sensitive_content


@pytest.mark.parametrize(
    ("sample", "expected_code"),
    [
        ("Please explain asyncio event loops in Python.", "en"),
        ("कृपया मुझे पाइथन में एसिंक प्रोग्रामिंग समझाइए।", "hi"),
        ("bhai python mein async code kaise kaam karta hai batao", "hinglish"),
        ("रउआ कइसन बानी, हमरा भोजपुरी में मदद चाहीं", "bho"),
        ("हमर मगही में एगो सवाल हई", "mag"),
        ("हमर मैथिली मे अहाँ से मदद चाही", "mai"),
        ("तुम्ही कसे आहात? मला मराठीत समजावून सांगा.", "mr"),
        ("अहं संस्कृतम् पठामि, कथम् भवति एतत्?", "sa"),
        ("আপনি কেমন আছেন? আমাকে বাংলায় সাহায্য করুন।", "bn"),
        ("মই অসমীয়াত সহায় বিচাৰিছোঁ আৰু বুজিব বিচাৰোঁ।", "as"),
        ("ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ? ਮੈਨੂੰ ਪੰਜਾਬੀ ਵਿੱਚ ਦੱਸੋ।", "pa"),
        ("તમે કેમ છો? મને ગુજરાતીમાં સમજાવો.", "gu"),
        ("ଆପଣ କେମିତି ଅଛନ୍ତି? ମୋତେ ଓଡ଼ିଆରେ ବୁଝାନ୍ତୁ।", "or"),
        ("நீங்கள் எப்படி இருக்கிறீர்கள்? தமிழில் விளக்குங்கள்.", "ta"),
        ("మీరు ఎలా ఉన్నారు? తెలుగులో వివరించండి.", "te"),
        ("ನೀವು ಹೇಗಿದ್ದೀರಿ? ಕನ್ನಡದಲ್ಲಿ ವಿವರಿಸಿ.", "kn"),
        ("നിങ്ങൾക്ക് സുഖമാണോ? മലയാളത്തിൽ വിശദീകരിക്കൂ.", "ml"),
        ("آپ کیسے ہیں؟ براہ کرم اردو میں سمجھائیں۔", "ur"),
    ],
)
def test_multilingual_detection_covers_indian_languages(sample: str, expected_code: str) -> None:
    profile = detect_language(sample)
    assert profile.code == expected_code


def test_persona_modes_and_switch_commands() -> None:
    assert len(PERSONAS) == 7
    assert detect_persona_switch_command("Hey Aspirant switch to Teacher Mode") == "teacher"
    assert detect_persona_switch_command("please enable coding expert mode") == "coding"
    assert detect_persona_switch_command("bhai government services mode lagao") == "gov"
    assert detect_persona_switch_command("explain lists in python") is None


def test_style_adapter_preserves_language_and_non_manipulation() -> None:
    lang = detect_language("yaar python bug aa raha hai, short mein batao")
    style = analyze_style("yaar python bug aa raha hai, short mein batao")
    assert style.tone == "casual"
    assert style.verbosity == "concise"
    prompt = build_system_instruction(get_persona("coding"), lang, style)
    assert "Hinglish" in prompt
    assert "concise" in prompt.lower()
    assert "Never manipulate" in prompt


def test_redactor_masks_aadhaar_pan_otp_and_keys() -> None:
    sample = "My Aadhaar is 2345 6789 0123, PAN is ABCDE1234F, OTP: 482910, key=AIzaSyD1234567890abcdefghij12345"
    assert contains_sensitive_secret(sample)
    res = redact_sensitive_content(sample)
    assert "2345 6789 0123" not in res.text
    assert "ABCDE1234F" not in res.text
    assert "482910" not in res.text
    assert "AIzaSy" not in res.text
    assert res.redacted_count == 4
