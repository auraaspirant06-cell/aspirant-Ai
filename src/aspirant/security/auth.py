"""Local PIN/passphrase authentication and Windows Hello availability helper."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import subprocess
import sys
from typing import Any

from aspirant.security.vault import SecretVault

_PBKDF2_ITERS = 300_000


def _hash_pin(pin: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, _PBKDF2_ITERS)
    return base64.b64encode(dk).decode("ascii")


def check_windows_hello_available() -> dict[str, Any]:
    """Check whether Windows Hello biometric/PIN verification is enrolled on this PC."""
    if sys.platform != "win32":
        return {"supported": False, "detail": "Windows Hello is Windows-only."}
    try:
        ps = (
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
            "$op = [Windows.Security.Credentials.UI.UserConsentVerifier,Windows.Security.Credentials.UI,ContentType=WindowsRuntime]::CheckAvailabilityAsync(); "
            "$task = [System.WindowsRuntimeSystemExtensions]::AsTask($op); "
            "$task.Wait(3000) | Out-Null; "
            "Write-Output $task.Result"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=6,
        )
        status = (proc.stdout or "").strip()
        return {
            "supported": status == "Available",
            "status": status or "Unavailable",
        }
    except Exception as exc:
        return {"supported": False, "status": f"Unavailable ({exc})"}


class LocalAuthManager:
    """Manages optional local lock PIN and session lock state via SecretVault."""

    def __init__(self, vault: SecretVault) -> None:
        self.vault = vault
        self._locked = False

    def is_pin_configured(self) -> bool:
        return bool(self.vault.get_secret("LOCAL_AUTH_HASH"))

    @property
    def is_locked(self) -> bool:
        return self._locked and self.is_pin_configured()

    def set_pin(self, pin: str) -> None:
        cleaned = pin.strip()
        if len(cleaned) < 4:
            raise ValueError("Local PIN/passphrase must be at least 4 characters.")
        salt = os.urandom(16)
        digest = _hash_pin(cleaned, salt)
        self.vault.set_secret("LOCAL_AUTH_SALT", base64.b64encode(salt).decode("ascii"))
        self.vault.set_secret("LOCAL_AUTH_HASH", digest)

    def clear_pin(self, current_pin: str) -> None:
        if not self.verify_pin(current_pin):
            raise PermissionError("Current PIN is incorrect.")
        self.vault.delete_secret("LOCAL_AUTH_SALT")
        self.vault.delete_secret("LOCAL_AUTH_HASH")
        self._locked = False

    def verify_pin(self, pin: str) -> bool:
        salt_b64 = self.vault.get_secret("LOCAL_AUTH_SALT")
        stored_hash = self.vault.get_secret("LOCAL_AUTH_HASH")
        if not salt_b64 or not stored_hash:
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"))
        candidate = _hash_pin(pin.strip(), salt)
        return hmac.compare_digest(candidate, stored_hash)

    def lock(self) -> bool:
        if not self.is_pin_configured():
            return False
        self._locked = True
        return True

    def unlock(self, pin: str) -> bool:
        if not self.is_pin_configured():
            self._locked = False
            return True
        if self.verify_pin(pin):
            self._locked = False
            return True
        return False

    def status(self) -> dict[str, Any]:
        return {
            "pin_configured": self.is_pin_configured(),
            "locked": self.is_locked,
        }
