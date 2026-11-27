"""Voice intelligence, continuous listening, command execution, and speaker recognition endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import AuthenticatedPrincipal, get_container, get_current_user, get_db_session
from backend.app.core.container import EcosystemContainer
from backend.app.domain.entities import ProductSource
from backend.app.voice.intelligence import (
    LANGUAGE_NAMES,
    SAME_LANGUAGE_GREETINGS,
    VoiceCommandRouter,
    detect_voice_language,
    evaluate_voice_signal,
)
from backend.app.voice.speaker_id import VoiceIdentityService


router = APIRouter(prefix="/voice", tags=["Voice Intelligence & Identity"])


class VoiceEnrollRequest(BaseModel):
    password: str = Field(min_length=1)
    label: str = "Primary Owner"
    samples: list[float] = Field(min_length=8)
    voice_unlock_enabled: bool = True
    confidence_threshold: float = Field(default=0.85, ge=0.5, le=0.99)


class VoiceVerifyRequest(BaseModel):
    samples: list[float] = Field(min_length=8)


class VoiceProcessRequest(BaseModel):
    transcript: str = Field(min_length=1)
    always_listening: bool = True
    signal_db: float = -18.0
    noise_db: float = -42.0
    far_field: bool = False
    barge_in: bool = False
    explicit_authorization: bool = False
    voice_samples: list[float] | None = None


@router.get("/languages")
async def supported_languages() -> dict:
    return {
        "count": len(LANGUAGE_NAMES),
        "languages": [{"code": k, "name": v} for k, v in LANGUAGE_NAMES.items()],
    }


@router.post("/identity/enroll")
async def enroll_speaker(
    body: VoiceEnrollRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    audit = container.build_audit_service(session)
    svc = VoiceIdentityService(session)
    try:
        profile = await svc.enroll_or_update(
            user_id=principal.user.id,
            password=body.password,
            label=body.label,
            samples=body.samples,
            voice_unlock_enabled=body.voice_unlock_enabled,
            confidence_threshold=body.confidence_threshold,
        )
    except PermissionError as exc:
        await audit.record(
            user_id=principal.user.id,
            action="voice.enroll",
            resource="voice_profile",
            outcome="denied",
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    await audit.record(
        user_id=principal.user.id,
        action="voice.enroll",
        resource="voice_profile",
        outcome="success",
        details={"voice_unlock_enabled": profile.voice_unlock_enabled},
    )
    return {
        "profile_id": profile.id,
        "label": profile.label,
        "voice_unlock_enabled": profile.voice_unlock_enabled,
        "confidence_threshold": profile.confidence_threshold,
        "security_note": "Password/JWT fallback required for any future voice profile updates.",
    }


@router.post("/identity/verify")
async def verify_speaker(
    body: VoiceVerifyRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    svc = VoiceIdentityService(session)
    res = await svc.verify_speaker(user_id=principal.user.id, samples=body.samples)
    return {
        "enrolled": res.enrolled,
        "verified": res.verified,
        "confidence": res.confidence,
        "voice_unlock_enabled": res.voice_unlock_enabled,
        "access_level": res.access_level,
        "profile_label": res.profile_label,
    }


@router.post("/process")
async def process_voice_utterance(
    body: VoiceProcessRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    lang_code, lang_name = detect_voice_language(body.transcript)
    signal = evaluate_voice_signal(
        transcript=body.transcript,
        signal_db=body.signal_db,
        noise_db=body.noise_db,
        far_field=body.far_field,
        barge_in=body.barge_in,
    )
    speaker = await VoiceIdentityService(session).verify_speaker(
        user_id=principal.user.id,
        samples=body.voice_samples,
    )
    cmd = VoiceCommandRouter().classify_and_authorize(
        transcript=body.transcript,
        explicit_authorization=body.explicit_authorization,
        speaker_access_level=speaker.access_level,
    )

    greeting = SAME_LANGUAGE_GREETINGS.get(lang_code, "Understood")
    if cmd.requires_authorization and not cmd.authorized:
        reply = f"{greeting} ({lang_name}): Sensitive action '{cmd.intent}' requires explicit authorization or verified owner identity."
    else:
        ai_res = await container.ai_router.generate(
            prompt=f"Reply strictly in {lang_name} ({lang_code}). User voice command: {body.transcript}",
            system_instruction=f"Respond naturally in {lang_name}. Keep voice response clear and interruptible.",
            task_type="fast",
        )
        reply = f"{greeting} ({lang_name}): {ai_res.text}"

    memory = container.build_memory_service(session)
    await memory.record_conversation_turn(
        user_id=principal.user.id,
        role="user",
        message=body.transcript,
        source_app=ProductSource.NOVA,
    )

    return {
        "language": lang_code,
        "language_name": lang_name,
        "always_listening": body.always_listening,
        "confidence": signal.confidence,
        "far_field_detected": signal.far_field_detected,
        "noise_filtered_snr_db": signal.noise_filtered_snr_db,
        "interrupt_active_tts": signal.should_interrupt_tts,
        "speaker_verified": speaker.verified,
        "speaker_confidence": speaker.confidence,
        "access_level": speaker.access_level,
        "detected_intent": cmd.intent,
        "sensitive": cmd.sensitive,
        "requires_authorization": cmd.requires_authorization,
        "authorized": cmd.authorized,
        "reply_text": reply,
    }
