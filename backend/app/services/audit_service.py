"""Audit logging & secrets posture reporting service."""

from __future__ import annotations

from backend.app.core.config import EcosystemSettings
from backend.app.domain.entities import AuditEventEntity, new_id
from backend.app.domain.repositories import AuditRepository


class AuditService:
    """Records and queries security audit trails with optional PII masking."""

    def __init__(self, audit_repo: AuditRepository, settings: EcosystemSettings) -> None:
        self._repo = audit_repo
        self._settings = settings

    @staticmethod
    def _redact(text: str) -> str:
        try:
            from aspirant.security.redactor import redact_sensitive_content

            return redact_sensitive_content(text).redacted_text
        except Exception:
            return text

    async def record(
        self,
        *,
        user_id: str | None,
        action: str,
        resource: str,
        outcome: str = "success",
        ip_address: str = "local",
        details: dict | None = None,
    ) -> AuditEventEntity:
        clean_details: dict = {}
        for k, v in (details or {}).items():
            clean_details[k] = self._redact(v) if isinstance(v, str) else v
        return await self._repo.log_event(
            AuditEventEntity(
                id=new_id(),
                user_id=user_id,
                action=action,
                resource=resource,
                outcome=outcome,
                ip_address=ip_address,
                details=clean_details,
            )
        )

    async def list_recent(self, user_id: str | None = None, limit: int = 100) -> list[AuditEventEntity]:
        return await self._repo.list_events(user_id=user_id, limit=limit)

    def security_posture(self) -> dict:
        return {
            "encryption_at_rest": "fernet-aes-hmac",
            "password_hashing": "argon2id",
            "jwt_algorithm": self._settings.jwt_algorithm,
            "https_enforced": self._settings.enforce_https,
            "rate_limit": f"{self._settings.rate_limit_requests}/{self._settings.rate_limit_window_seconds}s",
            "gemini_configured": bool(self._settings.gemini_api_key),
            "openai_configured": bool(self._settings.openai_api_key),
        }
