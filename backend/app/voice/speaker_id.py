"""Speaker enrollment, verification, and voice-unlock policy with mandatory password fallback."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import PasswordService
from backend.app.domain.entities import new_id
from backend.app.infrastructure.db.models import UserModel, VoiceProfileModel


VOICEPRINT_DIM = 16


def extract_voiceprint(samples: list[float] | None = None, passphrase: str = "") -> list[float]:
    """Compute normalized DCT harmonic/formant spectral + zero-crossing voiceprint vector."""
    if samples and len(samples) >= 4:
        n = len(samples)
        mean_val = sum(float(x) for x in samples) / n
        centered = [float(x) - mean_val for x in samples]
        vec = [0.0] * VOICEPRINT_DIM
        # Compute Type-II DCT frequency-band projections + first-difference cadence
        for k in range(1, VOICEPRINT_DIM + 1):
            dct_coeff = sum(
                centered[t] * math.cos(math.pi * k * (t + 0.5) / n)
                for t in range(n)
            )
            vec[k - 1] = dct_coeff / n
        # Encode zero-crossing cadence ratio into highest orthogonal dimensions
        zc_rate = sum(
            1.0
            for idx in range(1, n)
            if (samples[idx - 1] >= 0) != (samples[idx] >= 0)
        ) / max(1, n - 1)
        vec[-1] += zc_rate - 0.5
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [round(v / norm, 6) for v in vec]

    seed = hashlib.sha256((passphrase or "default-speaker").encode("utf-8")).digest()
    raw = [((b / 255.0) * 2.0 - 1.0) for b in seed[:VOICEPRINT_DIM]]
    norm = math.sqrt(sum(v * v for v in raw)) or 1.0
    return [round(v / norm, 6) for v in raw]


def voice_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return max(0.0, min(1.0, dot / (na * nb)))


@dataclass(slots=True)
class SpeakerVerificationResult:
    enrolled: bool
    verified: bool
    confidence: float
    voice_unlock_enabled: bool
    access_level: str  # "trusted" or "restricted"
    profile_label: str


class VoiceIdentityService:
    """Manages speaker recognition profiles with mandatory credential fallback on profile changes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enroll_or_update(
        self,
        *,
        user_id: str,
        password: str,
        label: str,
        samples: list[float],
        voice_unlock_enabled: bool = False,
        confidence_threshold: float = 0.85,
    ) -> VoiceProfileModel:
        """Enroll or modify trusted voice profile only after password fallback verification."""
        user = await self._session.get(UserModel, user_id)
        if not user or not PasswordService.verify_password(password, user.password_hash):
            raise PermissionError(
                "Modifying or enrolling a trusted voice profile requires valid account password verification."
            )

        embedding = extract_voiceprint(samples, label)
        stmt = select(VoiceProfileModel).where(VoiceProfileModel.user_id == user_id)
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.label = label.strip() or existing.label
            existing.embedding_json = embedding
            existing.voice_unlock_enabled = voice_unlock_enabled
            existing.confidence_threshold = max(0.5, min(0.99, confidence_threshold))
            row = existing
        else:
            row = VoiceProfileModel(
                id=new_id(),
                user_id=user_id,
                label=label.strip() or "Owner Voice",
                embedding_json=embedding,
                voice_unlock_enabled=voice_unlock_enabled,
                confidence_threshold=max(0.5, min(0.99, confidence_threshold)),
            )
            self._session.add(row)
        await self._session.flush()
        return row

    async def verify_speaker(
        self,
        *,
        user_id: str,
        samples: list[float] | None,
    ) -> SpeakerVerificationResult:
        stmt = select(VoiceProfileModel).where(VoiceProfileModel.user_id == user_id)
        profile = (await self._session.execute(stmt)).scalar_one_or_none()
        if not profile:
            return SpeakerVerificationResult(
                enrolled=False,
                verified=True,  # No voice lock enabled -> relies on standard JWT authentication
                confidence=1.0,
                voice_unlock_enabled=False,
                access_level="trusted",
                profile_label="none",
            )

        if not samples:
            # Voice unlock enabled without matching voiceprint -> restricted unless fallback auth is used
            return SpeakerVerificationResult(
                enrolled=True,
                verified=False,
                confidence=0.0,
                voice_unlock_enabled=profile.voice_unlock_enabled,
                access_level="restricted" if profile.voice_unlock_enabled else "trusted",
                profile_label=profile.label,
            )

        candidate = extract_voiceprint(samples, profile.label)
        score = round(voice_similarity(candidate, list(profile.embedding_json or [])), 4)
        verified = score >= profile.confidence_threshold
        access = "trusted" if (verified or not profile.voice_unlock_enabled) else "restricted"
        return SpeakerVerificationResult(
            enrolled=True,
            verified=verified,
            confidence=score,
            voice_unlock_enabled=profile.voice_unlock_enabled,
            access_level=access,
            profile_label=profile.label,
        )
