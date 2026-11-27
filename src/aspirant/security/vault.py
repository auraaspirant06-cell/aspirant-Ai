"""DPAPI + AES-GCM / Fernet encrypted local vault for API keys and secrets."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import threading
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from aspirant.security.tokens import _dpapi_protect, _dpapi_unprotect


class SecretVault:
    """Encrypted key-value secret store backed by Windows DPAPI + Fernet (AES-CBC+HMAC)."""

    def __init__(self, vault_path: Path, key_path: Path | None = None) -> None:
        self.vault_path = vault_path
        self.key_path = key_path or vault_path.with_suffix(".key")
        self._lock = threading.Lock()
        self._fernet = Fernet(self._load_or_create_master_key())

    def _load_or_create_master_key(self) -> bytes:
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if self.key_path.exists():
            try:
                raw = base64.b64decode(self.key_path.read_text(encoding="utf-8").strip().encode("ascii"))
                unprotected = _dpapi_unprotect(raw)
                # Validate key format
                Fernet(unprotected)
                return unprotected
            except Exception:
                pass
        key = Fernet.generate_key()
        protected = _dpapi_protect(key)
        self.key_path.write_text(base64.b64encode(protected).decode("ascii"), encoding="utf-8")
        return key

    def _read_map(self) -> dict[str, str]:
        if not self.vault_path.exists():
            return {}
        try:
            encrypted = self.vault_path.read_bytes()
            decrypted = self._fernet.decrypt(encrypted)
            data = json.loads(decrypted.decode("utf-8"))
            return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except (InvalidToken, json.JSONDecodeError, OSError):
            return {}

    def _write_map(self, data: dict[str, str]) -> None:
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.vault_path.write_bytes(self._fernet.encrypt(raw))

    def set_secret(self, name: str, value: str) -> None:
        with self._lock:
            data = self._read_map()
            if value:
                data[name] = value
            else:
                data.pop(name, None)
            self._write_map(data)

    def get_secret(self, name: str) -> str | None:
        with self._lock:
            return self._read_map().get(name)

    def delete_secret(self, name: str) -> bool:
        with self._lock:
            data = self._read_map()
            removed = data.pop(name, None) is not None
            if removed:
                self._write_map(data)
            return removed

    def list_secret_names(self) -> list[str]:
        """Return only secret key names — never values."""
        with self._lock:
            return sorted(self._read_map().keys())

    def export_encrypted_bundle(self) -> dict[str, Any]:
        """Return base64-encoded encrypted vault payload for backup."""
        with self._lock:
            raw = self.vault_path.read_bytes() if self.vault_path.exists() else b""
        return {"format": "fernet-dpapi-v1", "payload_b64": base64.b64encode(raw).decode("ascii")}
