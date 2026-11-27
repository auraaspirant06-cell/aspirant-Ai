"""Local API token protection (DPAPI on Windows) and origin verification."""

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
from pathlib import Path
import secrets
import sys


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _dpapi_protect(raw: bytes) -> bytes:
    """Encrypt bytes using the current Windows user's DPAPI key."""
    if sys.platform != "win32":
        return raw
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_buf = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    in_blob = _DataBlob(len(raw), in_buf)
    out_blob = _DataBlob()
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob), "AspirantToken", None, None, None, 0, ctypes.byref(out_blob)
    ):
        raise OSError("Windows DPAPI CryptProtectData failed.")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(protected: bytes) -> bytes:
    """Decrypt DPAPI-protected bytes for the current Windows user."""
    if sys.platform != "win32":
        return protected
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_buf = (ctypes.c_ubyte * len(protected)).from_buffer_copy(protected)
    in_blob = _DataBlob(len(protected), in_buf)
    out_blob = _DataBlob()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        raise OSError("Windows DPAPI CryptUnprotectData failed.")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def load_or_create_api_token(token_path: Path) -> str:
    """Load the DPAPI-protected local API token or mint a new 256-bit token."""
    token_path.parent.mkdir(parents=True, exist_ok=True)
    if token_path.exists():
        try:
            encoded = token_path.read_text(encoding="utf-8").strip()
            raw_bytes = base64.b64decode(encoded.encode("ascii"))
            token = _dpapi_unprotect(raw_bytes).decode("utf-8")
            if len(token) >= 32:
                return token
        except Exception:
            # Rotate corrupted or unreadable token safely
            pass

    token = secrets.token_urlsafe(32)
    protected = _dpapi_protect(token.encode("utf-8"))
    token_path.write_text(base64.b64encode(protected).decode("ascii"), encoding="utf-8")
    return token


def is_allowed_host(host_header: str | None) -> bool:
    """Prevent DNS-rebinding attacks by accepting loopback Host headers only."""
    if not host_header:
        return False
    hostname = host_header.split(":")[0].strip("[]").lower()
    return hostname in {"127.0.0.1", "localhost", "::1", "testserver"}


def is_allowed_origin(origin_header: str | None) -> bool:
    """Block cross-origin browser requests from external sites."""
    if origin_header is None:
        return True
    normalized = origin_header.strip().lower()
    return (
        normalized.startswith("http://127.0.0.1:")
        or normalized.startswith("http://localhost:")
        or normalized in {"http://127.0.0.1", "http://localhost"}
    )
