"""Voice intelligence, streaming companion dialogue, presets/cloning hooks, mic diagnostics & speaker ID."""

from __future__ import annotations

import json

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import AuthenticatedPrincipal, get_container, get_current_user, get_db_session
from backend.app.ai.system_prompt import build_aspirant_core_prompt, build_voice_confirmation, detect_interaction_mode
from backend.app.core.container import EcosystemContainer
from backend.app.domain.entities import ProductSource
from backend.app.voice.diagnostics import (
    diagnose_audio_devices,
    get_diagnostics_manager,
    reinitialize_audio_subsystem,
)
from backend.app.voice.intelligence import (
    LANGUAGE_NAMES,
    SAME_LANGUAGE_GREETINGS,
    VoiceCommandRouter,
    detect_voice_language,
    evaluate_voice_signal,
)
from backend.app.voice.presets import (
    VoiceCloneHookService,
    build_voice_preview,
    list_voice_presets,
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


class VoicePreviewRequest(BaseModel):
    preset_id: str = "aanya-warm"
    sample_text: str | None = None


class VoiceCloneHookRequest(BaseModel):
    password: str = Field(min_length=1)
    explicit_consent: bool = False
    voice_name: str = "Owner Custom Voice"
    reference_samples: list[float] = Field(min_length=8)


class VoiceProcessRequest(BaseModel):
    transcript: str = Field(min_length=1)
    always_listening: bool = True
    signal_db: float = -18.0
    noise_db: float = -42.0
    far_field: bool = False
    barge_in: bool = False
    explicit_authorization: bool = False
    voice_samples: list[float] | None = None
    remember_language: bool = True


@router.get("/languages")
async def supported_languages() -> dict:
    return {
        "count": len(LANGUAGE_NAMES),
        "languages": [{"code": k, "name": v} for k, v in LANGUAGE_NAMES.items()],
    }


@router.get("/presets")
async def get_voice_presets() -> dict:
    return {"presets": list_voice_presets()}


@router.post("/preview")
async def preview_voice(body: VoicePreviewRequest) -> dict:
    return build_voice_preview(body.preset_id, body.sample_text)


@router.get("/diagnostics/audio")
async def audio_diagnostics(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    return diagnose_audio_devices()


@router.post("/diagnostics/audio")
async def audio_diagnostics_with_samples(
    samples: list[float],
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    return diagnose_audio_devices(test_samples=samples)


# ---------------------------------------------------------------------------
# New Mic Diagnostics Endpoints
# ---------------------------------------------------------------------------


class ChangeMicRequest(BaseModel):
    device_index: int = Field(ge=0)


class TestMicRequest(BaseModel):
    device_index: int | None = None
    samples: list[float] | None = None


class VoiceMuteRequest(BaseModel):
    muted: bool


_VOICE_RUNTIME_STATE = {
    "listening_mode": "idle",
    "wake_word_armed": False,
    "noise_suppression_on": True,
    "muted": False,
}


@router.get("/diagnostics/devices")
async def list_audio_devices(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    """Full enumerated device list with type, driver status, permissions, and selected best mic."""
    return get_diagnostics_manager().discover()


@router.post("/diagnostics/test-mic")
async def test_microphone(
    body: TestMicRequest | list[float] | None = Body(default=None),
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    """Run live capture RMS test or evaluate supplied test samples."""
    dev_idx: int | None = None
    samples: list[float] | None = None
    if isinstance(body, list):
        samples = body or None
    elif isinstance(body, TestMicRequest):
        dev_idx = body.device_index
        samples = body.samples or None
    return get_diagnostics_manager().test_microphone(device_index=dev_idx, samples=samples)


@router.post("/diagnostics/change-mic")
async def change_microphone(
    body: ChangeMicRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    """Switch and persist the active microphone device index."""
    return get_diagnostics_manager().change_microphone(body.device_index)


@router.post("/diagnostics/recover")
async def recover_microphone(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    """Auto-recovery: rescan audio subsystem, try alternates, reconnect default/best mic."""
    return reinitialize_audio_subsystem()


@router.post("/mute")
async def set_voice_mute(
    body: VoiceMuteRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    """Toggle muted state reflected on the voice control dashboard."""
    _VOICE_RUNTIME_STATE["muted"] = body.muted
    return await voice_status(principal=principal)


@router.get("/status")
async def voice_status(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
) -> dict:
    """Live voice dashboard status: mic, listening mode, ASR, VAD, noise suppression."""
    mgr = get_diagnostics_manager()
    diag = mgr.discover()
    mic_connected = bool(diag["mic_available"])
    active = diag.get("active_device") or diag.get("best_device")
    muted = bool(_VOICE_RUNTIME_STATE["muted"])
    last_test = diag.get("last_test_result") or {}
    return {
        "listening_mode": "muted" if muted else _VOICE_RUNTIME_STATE["listening_mode"],
        "wake_word_armed": bool(_VOICE_RUNTIME_STATE["wake_word_armed"]),
        "asr_status": "muted" if muted else ("ready" if mic_connected else "unavailable"),
        "vad_active": False,
        "voice_activity_percent": int(last_test.get("volume_percent", 0)),
        "noise_suppression_on": bool(_VOICE_RUNTIME_STATE["noise_suppression_on"]),
        "muted": muted,
        "mic_connected": mic_connected,
        "mic_status": "MIC: CONNECTED" if mic_connected else "MIC: NOT FOUND",
        "current_device_index": active["index"] if active else None,
        "current_device_name": (active.get("display_name") or active["name"]) if active else "None",
        "current_device_type": active["device_type"] if active else "unknown",
        "driver_status": active.get("driver_status", "Unavailable") if active else "Unavailable",
        "sample_rate": int(active.get("default_samplerate", 0)) if active else 0,
        "permission": diag.get("permission", {}),
        "last_test_result": last_test or None,
        "health_status": diag["health_status"],
        "issues": diag["issues_detected"],
    }


@router.post("/clone/hook")
async def register_voice_clone_hook(
    body: VoiceCloneHookRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    svc = VoiceCloneHookService(session)
    try:
        return await svc.register_clone_hook(
            user_id=principal.user.id,
            password=body.password,
            explicit_consent=body.explicit_consent,
            voice_name=body.voice_name,
            reference_samples=body.reference_samples,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


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
    confirmation = build_voice_confirmation(body.transcript, owner_title="Boss")
    mode = detect_interaction_mode(body.transcript)
    if cmd.requires_authorization and not cmd.authorized:
        reply = f"{greeting} ({lang_name}): Sensitive action '{cmd.intent}' requires explicit authorization or verified owner identity."
    else:
        ai_res = await container.ai_router.generate(
            prompt=f"Reply strictly in {lang_name} ({lang_code}). User voice command: {body.transcript}",
            system_instruction=(
                f"{build_aspirant_core_prompt(owner_preferred_address='Boss', mode=mode)}\n\n"
                f"Respond naturally in {lang_name}. Keep voice response warm, clear, and interruptible."
            ),
            task_type="fast",
        )
        reply = f"{greeting} ({lang_name}): {ai_res.text}"

    memory = container.build_memory_service(session)
    if body.remember_language:
        await memory.set_preferences(
            principal.user.id,
            {"language_preference": lang_code},
        )
    await memory.record_conversation_turn(
        user_id=principal.user.id,
        role="user",
        message=body.transcript,
        source_app=ProductSource.NOVA,
    )

    return {
        "language": lang_code,
        "language_name": lang_name,
        "remembered_language": lang_code,
        "always_listening": body.always_listening,
        "confirmation": confirmation,
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


@router.post("/companion/stream")
async def companion_stream(
    body: VoiceProcessRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    lang_code, lang_name = detect_voice_language(body.transcript)
    ai_res = await container.ai_router.generate(
        prompt=f"Conversational reply in {lang_name}: {body.transcript}",
        system_instruction=f"Act as a human-like live voice companion in {lang_name}.",
        task_type="fast",
    )
    greeting = SAME_LANGUAGE_GREETINGS.get(lang_code, "Understood")
    full_reply = f"{greeting} — {ai_res.text}"
    words = full_reply.split(" ")

    async def event_gen():
        for idx, word in enumerate(words):
            chunk = {"index": idx, "token": word, "language": lang_code, "interruptible": True}
            yield f"data: {json.dumps(chunk)}\n\n"
        yield f"data: {json.dumps({'done': True, 'language': lang_code})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
