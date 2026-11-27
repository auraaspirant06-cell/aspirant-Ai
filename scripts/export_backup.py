"""CLI utility to export an encrypted ASPIRANT AI backup (.aspbk)."""

from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path

from aspirant.core.config import AppSettings
from aspirant.security.backup import create_encrypted_backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an encrypted ASPIRANT AI backup archive.")
    parser.add_argument("--out", type=Path, default=None, help="Optional output .aspbk file path")
    args = parser.parse_args()

    cfg = AppSettings()
    passphrase = getpass("Enter backup passphrase (min 6 chars): ")
    res = create_encrypted_backup(cfg.resolved_data_dir, passphrase, out_file=args.out)
    print(f"Backup written to: {res['path']} ({res['bytes']} bytes, files={res['files']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
