"""CLI entrypoint for repository self-healing diagnostics, static scan, and auto-repair."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app  # noqa: E402
from backend.app.self_healing.healer import RepositorySelfHealer  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Aspirant AI Self-Healing Diagnostics & Repair")
    parser.add_argument("--repair", action="store_true", help="Automatically repair fixable repository issues")
    args = parser.parse_args()

    api_paths = set(app.openapi().get("paths", {}).keys())
    report = RepositorySelfHealer(ROOT).run_audit(repair=args.repair, app_routes_paths=api_paths)
    print(json.dumps(report.to_dict(), indent=2))
    return 1 if report.overall_status == "degraded" else 0


if __name__ == "__main__":
    raise SystemExit(main())
