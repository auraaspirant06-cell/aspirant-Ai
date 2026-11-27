"""Password-encrypted backup and rollback-safe restore for Aspirant data."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import zipfile
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


def _derive_fernet_key(passphrase: str, salt: bytes) -> bytes:
    dk = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 480_000, dklen=32)
    return base64.urlsafe_b64encode(dk)


def create_encrypted_backup(
    data_dir: Path,
    passphrase: str,
    out_file: Path | None = None,
) -> dict[str, Any]:
    """Bundle memory.db, audit.db, and vault files into an encrypted .aspbk archive."""
    if len(passphrase.strip()) < 6:
        raise ValueError("Backup passphrase must be at least 6 characters.")

    data_root = data_dir.resolve()
    backups_dir = data_root / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    target = out_file or (
        backups_dir / f"aspirant_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.aspbk"
    )

    buf = io.BytesIO()
    included: list[str] = []
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in ("memory.db", "audit.db", "vault.enc", "vault.key"):
            fpath = data_root / fname
            if fpath.is_file():
                zf.write(fpath, arcname=fname)
                included.append(fname)

    salt = os.urandom(16)
    token = Fernet(_derive_fernet_key(passphrase.strip(), salt)).encrypt(buf.getvalue())
    envelope = {
        "format": "aspirant-backup-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "payload_b64": base64.b64encode(token).decode("ascii"),
        "files": included,
    }
    target.write_text(json.dumps(envelope), encoding="utf-8")
    return {"path": str(target), "files": included, "bytes": target.stat().st_size}


def restore_encrypted_backup(
    backup_file: Path,
    passphrase: str,
    target_data_dir: Path,
) -> dict[str, Any]:
    """Decrypt and restore an Aspirant backup after saving a rollback snapshot."""
    envelope = json.loads(backup_file.read_text(encoding="utf-8"))
    if envelope.get("format") != "aspirant-backup-v1":
        raise ValueError("Unsupported backup format.")

    salt = base64.b64decode(envelope["salt_b64"].encode("ascii"))
    payload = base64.b64decode(envelope["payload_b64"].encode("ascii"))
    try:
        zip_bytes = Fernet(_derive_fernet_key(passphrase.strip(), salt)).decrypt(payload)
    except InvalidToken as exc:
        raise PermissionError("Invalid backup passphrase or corrupted backup file.") from exc

    target_root = target_data_dir.resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    rollback_dir = target_root / "rollback_pre_restore"
    rollback_dir.mkdir(parents=True, exist_ok=True)
    for fname in ("memory.db", "audit.db", "vault.enc", "vault.key"):
        cur = target_root / fname
        if cur.is_file():
            shutil.copy2(cur, rollback_dir / fname)

    restored: list[str] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        for member in zf.namelist():
            if member not in {"memory.db", "audit.db", "vault.enc", "vault.key"}:
                continue
            (target_root / member).write_bytes(zf.read(member))
            restored.append(member)

    return {"restored_files": restored, "rollback_dir": str(rollback_dir)}
