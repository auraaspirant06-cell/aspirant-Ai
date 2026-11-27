"""Authentication & multi-device session service with refresh token rotation."""

from __future__ import annotations

from datetime import datetime, timezone

import jwt

from backend.app.core.security import JWTService, PasswordService, constant_time_equals
from backend.app.domain.entities import (
    AuditEventEntity,
    RefreshSessionEntity,
    UserEntity,
    new_id,
    utc_now,
)
from backend.app.domain.repositories import (
    AuditRepository,
    SessionRepository,
    UserRepository,
)


class AuthService:
    """Handles user registration, Argon2 password verification, JWT issuance, and refresh token rotation."""

    def __init__(
        self,
        *,
        users: UserRepository,
        sessions: SessionRepository,
        audit: AuditRepository,
        jwt_service: JWTService,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._audit = audit
        self._jwt = jwt_service

    async def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        device_name: str = "primary-desktop",
        device_platform: str = "windows",
        ip_address: str = "local",
    ) -> dict:
        existing = await self._users.get_by_email(email)
        if existing:
            raise ValueError("An account with this email already exists")

        user = UserEntity(
            id=new_id(),
            email=email.lower().strip(),
            full_name=full_name.strip() or "Aspirant User",
            password_hash=PasswordService.hash_password(password),
            role="owner",
            preferences={"theme": "dark", "voice": "female-natural", "language": "en"},
        )
        await self._users.create(user)
        tokens = await self._issue_session_tokens(
            user=user,
            device_name=device_name,
            device_platform=device_platform,
        )
        await self._audit.log_event(
            AuditEventEntity(
                id=new_id(),
                user_id=user.id,
                action="auth.register",
                resource="user",
                outcome="success",
                ip_address=ip_address,
                details={"device_platform": device_platform},
            )
        )
        return {"user": user, **tokens}

    async def login(
        self,
        *,
        email: str,
        password: str,
        device_name: str = "client",
        device_platform: str = "web",
        ip_address: str = "local",
    ) -> dict:
        user = await self._users.get_by_email(email)
        if not user or not PasswordService.verify_password(password, user.password_hash):
            await self._audit.log_event(
                AuditEventEntity(
                    id=new_id(),
                    user_id=user.id if user else None,
                    action="auth.login",
                    resource="session",
                    outcome="denied",
                    ip_address=ip_address,
                    details={"email": email.lower().strip()},
                )
            )
            raise PermissionError("Invalid email or password")

        if not user.is_active:
            raise PermissionError("Account is disabled")

        tokens = await self._issue_session_tokens(
            user=user,
            device_name=device_name,
            device_platform=device_platform,
        )
        await self._audit.log_event(
            AuditEventEntity(
                id=new_id(),
                user_id=user.id,
                action="auth.login",
                resource="session",
                outcome="success",
                ip_address=ip_address,
                details={"device_name": device_name, "device_platform": device_platform},
            )
        )
        return {"user": user, **tokens}

    async def refresh(self, *, refresh_token: str, ip_address: str = "local") -> dict:
        try:
            payload = self._jwt.decode_token(refresh_token, expected_type="refresh")
        except jwt.InvalidTokenError as exc:
            raise PermissionError("Invalid or expired refresh token") from exc

        session_id = str(payload.get("sid", ""))
        user_id = str(payload.get("sub", ""))
        session = await self._sessions.get_by_id(session_id)
        if not session or session.revoked or session.user_id != user_id:
            if session_id:
                await self._sessions.revoke_all_for_user(user_id)
            raise PermissionError("Refresh session revoked or reused")

        expires = session.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            await self._sessions.revoke(session.id)
            raise PermissionError("Refresh session expired")

        presented_hash = self._jwt.hash_token(refresh_token)
        if not constant_time_equals(presented_hash, session.token_hash):
            await self._sessions.revoke_all_for_user(user_id)
            raise PermissionError("Refresh token mismatch — all sessions revoked")

        user = await self._users.get_by_id(user_id)
        if not user or not user.is_active:
            raise PermissionError("User unavailable")

        # Rotate token cleanly
        await self._sessions.revoke(session.id)
        tokens = await self._issue_session_tokens(
            user=user,
            device_name=session.device_name,
            device_platform=session.device_platform,
        )
        await self._audit.log_event(
            AuditEventEntity(
                id=new_id(),
                user_id=user.id,
                action="auth.refresh",
                resource="session",
                outcome="success",
                ip_address=ip_address,
            )
        )
        return {"user": user, **tokens}

    async def logout(self, *, refresh_token: str, ip_address: str = "local") -> None:
        try:
            payload = self._jwt.decode_token(refresh_token, expected_type="refresh")
        except jwt.InvalidTokenError:
            return
        sid = str(payload.get("sid", ""))
        uid = payload.get("sub")
        if sid:
            await self._sessions.revoke(sid)
        await self._audit.log_event(
            AuditEventEntity(
                id=new_id(),
                user_id=uid,
                action="auth.logout",
                resource="session",
                outcome="success",
                ip_address=ip_address,
            )
        )

    async def _issue_session_tokens(
        self, *, user: UserEntity, device_name: str, device_platform: str
    ) -> dict:
        session_id = new_id()
        access_token = self._jwt.create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
            device_id=session_id,
        )
        refresh_token, expires_at = self._jwt.create_refresh_token(
            user_id=user.id,
            session_id=session_id,
        )
        await self._sessions.create(
            RefreshSessionEntity(
                id=session_id,
                user_id=user.id,
                token_hash=self._jwt.hash_token(refresh_token),
                device_name=device_name,
                device_platform=device_platform,
                revoked=False,
                expires_at=expires_at,
                created_at=utc_now(),
            )
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "session_id": session_id,
        }
