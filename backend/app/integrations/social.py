"""Official, TOS-compliant modular social platform connectors with encrypted tokens & rate limits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import EncryptionAtRest, SlidingWindowRateLimiter
from backend.app.domain.entities import new_id
from backend.app.infrastructure.db.models import SocialConnectionModel


@dataclass(frozen=True, slots=True)
class PlatformSpec:
    platform: str
    display_name: str
    official_base_url: str
    supported_permissions: tuple[str, ...]
    rate_limit_per_minute: int


OFFICIAL_PLATFORMS: dict[str, PlatformSpec] = {
    "telegram": PlatformSpec(
        platform="telegram",
        display_name="Telegram Bot API",
        official_base_url="https://api.telegram.org",
        supported_permissions=("read", "publish", "webhook"),
        rate_limit_per_minute=30,
    ),
    "youtube": PlatformSpec(
        platform="youtube",
        display_name="YouTube Data API v3",
        official_base_url="https://www.googleapis.com/youtube/v3",
        supported_permissions=("read", "publish", "analytics"),
        rate_limit_per_minute=20,
    ),
    "instagram": PlatformSpec(
        platform="instagram",
        display_name="Instagram Business Graph API",
        official_base_url="https://graph.facebook.com/v21.0",
        supported_permissions=("read", "publish", "insights"),
        rate_limit_per_minute=15,
    ),
    "discord": PlatformSpec(
        platform="discord",
        display_name="Discord REST API v10",
        official_base_url="https://discord.com/api/v10",
        supported_permissions=("read", "publish", "webhook"),
        rate_limit_per_minute=30,
    ),
    "x": PlatformSpec(
        platform="x",
        display_name="X Platform API v2",
        official_base_url="https://api.x.com/2",
        supported_permissions=("read", "publish"),
        rate_limit_per_minute=12,
    ),
}


class SocialIntegrationManager:
    """Manages official API credentials, permissions, rate limiting, and webhook event processing."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        crypto: EncryptionAtRest,
        rate_limiter: SlidingWindowRateLimiter | None = None,
    ) -> None:
        self._session = session
        self._crypto = crypto
        self._limiters: dict[str, SlidingWindowRateLimiter] = {
            name: SlidingWindowRateLimiter(max_requests=spec.rate_limit_per_minute, window_seconds=60)
            for name, spec in OFFICIAL_PLATFORMS.items()
        }
        if rate_limiter is not None:
            for key in self._limiters:
                self._limiters[key] = rate_limiter

    def _spec(self, platform: str) -> PlatformSpec:
        key = platform.lower().strip()
        if key not in OFFICIAL_PLATFORMS:
            raise ValueError(f"Unsupported social platform: {platform}")
        return OFFICIAL_PLATFORMS[key]

    async def catalog(self, user_id: str) -> list[dict[str, Any]]:
        rows = (
            await self._session.execute(
                select(SocialConnectionModel).where(SocialConnectionModel.user_id == user_id)
            )
        ).scalars().all()
        by_plat = {r.platform: r for r in rows}
        out: list[dict[str, Any]] = []
        for plat, spec in OFFICIAL_PLATFORMS.items():
            conn = by_plat.get(plat)
            out.append(
                {
                    "platform": plat,
                    "display_name": spec.display_name,
                    "official_base_url": spec.official_base_url,
                    "connected": bool(conn and conn.is_enabled),
                    "permissions": list(conn.permissions_json or []) if conn else [],
                    "supported_permissions": list(spec.supported_permissions),
                    "rate_limit_per_minute": spec.rate_limit_per_minute,
                }
            )
        return out

    async def connect(
        self,
        *,
        user_id: str,
        platform: str,
        access_token: str,
        permissions: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> SocialConnectionModel:
        spec = self._spec(platform)
        valid_perms = [p for p in permissions if p in spec.supported_permissions] or ["read"]
        encrypted = self._crypto.encrypt(access_token.strip())
        stmt = select(SocialConnectionModel).where(
            SocialConnectionModel.user_id == user_id,
            SocialConnectionModel.platform == spec.platform,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row:
            row.access_token_encrypted = encrypted
            row.permissions_json = valid_perms
            row.is_enabled = True
            row.metadata_json = metadata or row.metadata_json
        else:
            row = SocialConnectionModel(
                id=new_id(),
                user_id=user_id,
                platform=spec.platform,
                access_token_encrypted=encrypted,
                permissions_json=valid_perms,
                is_enabled=True,
                metadata_json=metadata or {},
            )
            self._session.add(row)
        await self._session.flush()
        return row

    async def disconnect(self, *, user_id: str, platform: str) -> bool:
        spec = self._spec(platform)
        stmt = select(SocialConnectionModel).where(
            SocialConnectionModel.user_id == user_id,
            SocialConnectionModel.platform == spec.platform,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if not row:
            return False
        row.is_enabled = False
        row.access_token_encrypted = ""
        await self._session.flush()
        return True

    async def dispatch_action(
        self,
        *,
        user_id: str,
        platform: str,
        required_permission: str,
        payload: dict[str, Any],
        live_send: bool = False,
    ) -> dict[str, Any]:
        spec = self._spec(platform)
        stmt = select(SocialConnectionModel).where(
            SocialConnectionModel.user_id == user_id,
            SocialConnectionModel.platform == spec.platform,
        )
        conn = (await self._session.execute(stmt)).scalar_one_or_none()
        if not conn or not conn.is_enabled:
            raise PermissionError(f"Connector '{spec.platform}' is not connected or is disabled.")
        if required_permission not in (conn.permissions_json or []):
            raise PermissionError(
                f"Connector '{spec.platform}' lacks '{required_permission}' permission."
            )

        allowed, remaining = self._limiters[spec.platform].allow(f"{user_id}:{spec.platform}")
        if not allowed:
            raise RuntimeError(f"Rate limit exceeded for official {spec.display_name} connector.")

        token = self._crypto.decrypt(conn.access_token_encrypted)
        if not token:
            raise PermissionError("Stored connector token is missing or cleared.")

        if not live_send:
            return {
                "platform": spec.platform,
                "status": "validated_ready",
                "official_endpoint": spec.official_base_url,
                "rate_limit_remaining": remaining,
                "payload_preview": payload,
            }

        # Official REST endpoint invocation using user's stored token
        endpoint = spec.official_base_url
        if spec.platform == "telegram":
            endpoint = f"{spec.official_base_url}/bot{token}/sendMessage"
            headers = {"Content-Type": "application/json"}
        else:
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if spec.platform == "discord" and payload.get("channel_id"):
                endpoint = f"{spec.official_base_url}/channels/{payload['channel_id']}/messages"
            elif spec.platform == "x":
                endpoint = f"{spec.official_base_url}/tweets"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
            return {
                "platform": spec.platform,
                "status": "dispatched",
                "http_status": resp.status_code,
                "rate_limit_remaining": remaining,
            }

    def normalize_webhook_event(self, *, platform: str, raw_event: dict[str, Any]) -> dict[str, Any]:
        spec = self._spec(platform)
        text = (
            raw_event.get("text")
            or (raw_event.get("message") or {}).get("text")
            or raw_event.get("content")
            or ""
        )
        sender = (
            raw_event.get("sender")
            or ((raw_event.get("message") or {}).get("from") or {}).get("username")
            or raw_event.get("author_id")
            or "unknown"
        )
        return {
            "platform": spec.platform,
            "official_source": spec.display_name,
            "sender": str(sender),
            "text": str(text)[:2000],
            "event_type": str(raw_event.get("type", "message")),
        }
