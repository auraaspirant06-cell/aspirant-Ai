"""Security primitives: Argon2 hashing, JWT + Refresh Tokens, encryption at rest, rate limiting, HTTPS middleware."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse

from backend.app.core.config import EcosystemSettings


_PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)


class PasswordService:
    """Hashes and verifies user credentials using Argon2id."""

    @staticmethod
    def hash_password(password: str) -> str:
        return _PASSWORD_HASHER.hash(password)

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        try:
            return _PASSWORD_HASHER.verify(hashed, password)
        except VerifyMismatchError:
            return False


class EncryptionAtRest:
    """Symmetric authenticated encryption (Fernet AES-128-CBC + HMAC-SHA256) for sensitive DB fields & secrets."""

    def __init__(self, master_key: str | None = None) -> None:
        raw_secret = (master_key or secrets.token_urlsafe(32)).encode("utf-8")
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw_secret).digest())
        self._fernet = Fernet(derived)

    def encrypt(self, plaintext: str) -> str:
        if plaintext == "":
            return ""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        if ciphertext == "":
            return ""
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Unable to decrypt stored payload with current key") from exc


class JWTService:
    """Issues and validates short-lived JWT access tokens and rotatable refresh tokens."""

    def __init__(self, settings: EcosystemSettings) -> None:
        self._secret = settings.jwt_secret_key
        self._alg = settings.jwt_algorithm
        self._access_mins = settings.access_token_expire_minutes
        self._refresh_days = settings.refresh_token_expire_days

    def create_access_token(
        self,
        *,
        user_id: str,
        email: str,
        role: str = "owner",
        device_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": user_id,
            "email": email,
            "role": role,
            "type": "access",
            "jti": secrets.token_hex(16),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=self._access_mins)).timestamp()),
        }
        if device_id:
            payload["device_id"] = device_id
        if extra:
            payload.update(extra)
        return jwt.encode(payload, self._secret, algorithm=self._alg)

    def create_refresh_token(self, *, user_id: str, session_id: str) -> tuple[str, datetime]:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=self._refresh_days)
        payload = {
            "sub": user_id,
            "sid": session_id,
            "type": "refresh",
            "jti": secrets.token_hex(16),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._alg), expires_at

    def decode_token(self, token: str, expected_type: str | None = None) -> dict[str, Any]:
        payload = jwt.decode(token, self._secret, algorithms=[self._alg])
        if expected_type and payload.get("type") != expected_type:
            raise jwt.InvalidTokenError(f"Expected {expected_type} token")
        return payload

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SlidingWindowRateLimiter:
    """In-process sliding-window rate limiter with optional Redis counter mirroring."""

    def __init__(self, max_requests: int = 120, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        bucket = self._buckets[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            return False, 0
        bucket.append(now)
        return True, self.max_requests - len(bucket)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces strict transport headers, optional HTTPS redirect, and sliding-window rate limits."""

    def __init__(
        self,
        app: Any,
        *,
        settings: EcosystemSettings,
        rate_limiter: SlidingWindowRateLimiter,
    ) -> None:
        super().__init__(app)
        self._settings = settings
        self._rate_limiter = rate_limiter

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Optional strict HTTPS redirect (skipped for loopback local dev/test hosts)
        host = (request.headers.get("host") or "").split(":")[0].lower()
        proto = (request.headers.get("x-forwarded-proto") or request.url.scheme).lower()
        if (
            self._settings.enforce_https
            and proto != "https"
            and host not in {"localhost", "127.0.0.1", "testserver"}
        ):
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(https_url), status_code=307)

        client_ip = request.client.host if request.client else "local"
        allowed, remaining = self._rate_limiter.allow(f"{client_ip}:{request.url.path}")
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please slow down."},
                headers={"Retry-After": str(self._settings.rate_limit_window_seconds)},
            )

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=()"
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        if self._settings.enforce_https:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
