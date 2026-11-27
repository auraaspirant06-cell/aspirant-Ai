"""Self-healing engine: detects & repairs broken imports, migrations, routes, contracts, Docker & security issues."""

from __future__ import annotations

import ast
import importlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlalchemy
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(slots=True)
class HealCheckResult:
    name: str
    status: str  # "ok", "warn", "repaired", "failed"
    detail: str
    repairable: bool = False
    suggested_fix: str = ""


@dataclass(slots=True)
class SelfHealReport:
    overall_status: str
    checks: list[HealCheckResult] = field(default_factory=list)
    repaired: list[str] = field(default_factory=list)
    security_findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "detail": c.detail,
                    "repairable": c.repairable,
                    "suggested_fix": c.suggested_fix,
                }
                for c in self.checks
            ],
            "repaired": self.repaired,
            "security_findings": self.security_findings,
        }


class RepositorySelfHealer:
    """Runs repository-wide diagnostics and applies idempotent, safe repairs."""

    def __init__(self, root: Path = REPO_ROOT) -> None:
        self.root = root

    def check_dependencies(self) -> HealCheckResult:
        required = ("fastapi", "sqlalchemy", "alembic", "jwt", "argon2", "qdrant_client", "chromadb", "celery")
        missing = []
        for mod in required:
            try:
                importlib.import_module(mod)
            except Exception as exc:
                missing.append(f"{mod} ({exc})")
        sa_ver = sqlalchemy.__version__
        if missing:
            return HealCheckResult(
                name="dependencies",
                status="failed",
                detail=f"Broken imports: {missing}",
                suggested_fix="Run `uv sync` with sqlalchemy>=2.0.36,<2.1",
            )
        return HealCheckResult(
            name="dependencies",
            status="ok",
            detail=f"All core dependencies importable (SQLAlchemy {sa_ver}).",
        )

    def check_and_repair_alembic(self, *, repair: bool = False) -> tuple[HealCheckResult, list[str]]:
        repaired: list[str] = []
        backend_ini = self.root / "backend" / "alembic.ini"
        root_ini = self.root / "alembic.ini"
        mig_dir = self.root / "backend" / "migrations"
        vers_dir = mig_dir / "versions"

        if not mig_dir.exists() or not vers_dir.exists():
            return (
                HealCheckResult(
                    name="alembic_paths",
                    status="failed",
                    detail="Missing backend/migrations or versions directory.",
                    suggested_fix="Run `alembic init` or restore migrations directory.",
                ),
                repaired,
            )

        issues: list[str] = []
        if backend_ini.exists():
            txt = backend_ini.read_text(encoding="utf-8")
            if "script_location = migrations\n" in txt and "%(here)s" not in txt:
                if repair:
                    txt = txt.replace(
                        "script_location = migrations\n",
                        "script_location = %(here)s/migrations\n",
                    )
                    backend_ini.write_text(txt, encoding="utf-8")
                    repaired.append("Repaired script_location in backend/alembic.ini")
                else:
                    issues.append("backend/alembic.ini uses CWD-relative script_location")
        else:
            issues.append("Missing backend/alembic.ini")

        if not root_ini.exists():
            if repair and backend_ini.exists():
                content = backend_ini.read_text(encoding="utf-8").replace(
                    "%(here)s/migrations", "%(here)s/backend/migrations"
                ).replace("%(here)s/..", "%(here)s")
                root_ini.write_text(content, encoding="utf-8")
                repaired.append("Regenerated root alembic.ini")
            else:
                issues.append("Missing root alembic.ini")

        if issues:
            return (
                HealCheckResult(
                    name="alembic_paths",
                    status="warn",
                    detail="; ".join(issues),
                    repairable=True,
                    suggested_fix="Normalize script_location with %(here)s",
                ),
                repaired,
            )
        status = "repaired" if repaired else "ok"
        return (
            HealCheckResult(
                name="alembic_paths",
                status=status,
                detail="Both root and backend Alembic configs resolve migrations & versions cleanly.",
            ),
            repaired,
        )

    def check_python_ast_and_security(self) -> tuple[HealCheckResult, list[str]]:
        syntax_errors: list[str] = []
        security_findings: list[str] = []
        scan_roots = [self.root / "backend" / "app", self.root / "apps"]
        secret_regex = re.compile(r"(?i)(api_key|secret_key|password)\s*=\s*['\"][A-Za-z0-9_\-]{12,}['\"]")

        file_count = 0
        for base in scan_roots:
            if not base.exists():
                continue
            for py_file in base.rglob("*.py"):
                file_count += 1
                src = py_file.read_text(encoding="utf-8")
                try:
                    tree = ast.parse(src, filename=str(py_file))
                except SyntaxError as exc:
                    syntax_errors.append(f"{py_file.name}: {exc}")
                    continue

                rel = py_file.relative_to(self.root).as_posix()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        if node.func.id in {"eval", "exec"}:
                            security_findings.append(f"Avoid {node.func.id}() in {rel}:{node.lineno}")
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        if node.func.attr in {"run", "Popen"}:
                            for kw in node.keywords:
                                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                    security_findings.append(f"shell=True in {rel}:{node.lineno}")
                for line_no, line in enumerate(src.splitlines(), start=1):
                    if secret_regex.search(line):
                        security_findings.append(f"Potential hardcoded literal in {rel}:{line_no}")

        if syntax_errors:
            return (
                HealCheckResult(name="python_ast", status="failed", detail="; ".join(syntax_errors)),
                security_findings,
            )
        return (
            HealCheckResult(
                name="python_ast_security",
                status="warn" if security_findings else "ok",
                detail=f"Scanned {file_count} backend Python modules cleanly ({len(security_findings)} security notes).",
            ),
            security_findings,
        )

    def check_ui_routes(self) -> HealCheckResult:
        routes_ts = self.root / "frontend" / "src" / "lib" / "routes.ts"
        app_dir = self.root / "frontend" / "src" / "app"
        if not routes_ts.exists() or not app_dir.exists():
            return HealCheckResult(
                name="ui_routes",
                status="warn",
                detail="Frontend route registry missing.",
                suggested_fix="Create frontend/src/lib/routes.ts",
            )
        content = routes_ts.read_text(encoding="utf-8")
        hrefs = re.findall(r'href:\s*"([^"]+)"', content)
        missing_pages = []
        for href in hrefs:
            expected = app_dir / "page.tsx" if href == "/" else app_dir / href.lstrip("/") / "page.tsx"
            if not expected.exists():
                missing_pages.append(href)
        if missing_pages or len(hrefs) != len(set(hrefs)):
            return HealCheckResult(
                name="ui_routes",
                status="failed",
                detail=f"Route integrity failure: missing={missing_pages}",
                suggested_fix="Run `npm run validate:routes` inside frontend/",
            )
        return HealCheckResult(
            name="ui_routes",
            status="ok",
            detail=f"All {len(hrefs)} registered UI routes map uniquely to App Router pages.",
        )

    def check_api_contracts(self, app_routes_paths: set[str] | None = None) -> HealCheckResult:
        api_ts = self.root / "frontend" / "src" / "lib" / "api.ts"
        if not api_ts.exists():
            return HealCheckResult(name="api_contracts", status="warn", detail="frontend/src/lib/api.ts missing")
        src = api_ts.read_text(encoding="utf-8")
        called = set(re.findall(r'requestJson[^(]*\(\s*["`]([^"`?$]+)', src))
        if app_routes_paths is None:
            return HealCheckResult(
                name="api_contracts",
                status="ok",
                detail=f"Tracked {len(called)} frontend client API endpoints.",
            )
        mismatches = [p for p in sorted(called) if f"/api/v1{p}" not in app_routes_paths]
        if mismatches:
            return HealCheckResult(
                name="api_contracts",
                status="failed",
                detail=f"Frontend calls missing backend endpoints: {mismatches}",
                suggested_fix="Align frontend/src/lib/api.ts with FastAPI router paths.",
            )
        return HealCheckResult(
            name="api_contracts",
            status="ok",
            detail=f"Verified all {len(called)} frontend API calls match OpenAPI routes.",
        )

    def check_docker_configs(self) -> HealCheckResult:
        compose = self.root / "infrastructure" / "docker-compose.yml"
        dockerfiles = [
            self.root / "infrastructure" / "docker" / "backend.Dockerfile",
            self.root / "infrastructure" / "docker" / "frontend.Dockerfile",
        ]
        missing = [str(p.name) for p in dockerfiles if not p.exists()]
        if not compose.exists() or missing:
            return HealCheckResult(
                name="docker_config",
                status="failed",
                detail=f"Missing Docker files: {missing}",
            )
        data = yaml.safe_load(compose.read_text(encoding="utf-8"))
        services = list((data or {}).get("services", {}).keys())
        return HealCheckResult(
            name="docker_config",
            status="ok",
            detail=f"Docker Compose valid with {len(services)} services: {', '.join(services)}.",
        )

    def run_audit(self, *, repair: bool = False, app_routes_paths: set[str] | None = None) -> SelfHealReport:
        checks: list[HealCheckResult] = []
        repaired: list[str] = []

        checks.append(self.check_dependencies())
        alembic_res, alembic_repairs = self.check_and_repair_alembic(repair=repair)
        checks.append(alembic_res)
        repaired.extend(alembic_repairs)

        ast_res, sec_findings = self.check_python_ast_and_security()
        checks.append(ast_res)
        checks.append(self.check_ui_routes())
        checks.append(self.check_api_contracts(app_routes_paths))
        checks.append(self.check_docker_configs())

        data_dir = self.root / "data"
        if not data_dir.exists() and repair:
            data_dir.mkdir(parents=True, exist_ok=True)
            repaired.append("Created missing data/ runtime directory")

        overall = "healthy"
        if any(c.status == "failed" for c in checks):
            overall = "degraded"
        elif repaired:
            overall = "repaired"

        return SelfHealReport(
            overall_status=overall,
            checks=checks,
            repaired=repaired,
            security_findings=sec_findings,
        )


class CrashRecoveryJournal:
    """Captures unhandled runtime crashes safely and cleans stale locks during self-recovery."""

    def __init__(self, root: Path = REPO_ROOT) -> None:
        self.root = root
        self.journal_path = root / "data" / "crash_recovery.jsonl"

    def record_crash(self, *, path: str, error: str) -> None:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": path,
            "error": error[:400],
        }
        with self.journal_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    def list_crashes(self, limit: int = 25) -> list[dict[str, str]]:
        if not self.journal_path.exists():
            return []
        lines = self.journal_path.read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(line) for line in lines if line.strip()]

    def recover(self) -> dict[str, Any]:
        cleaned: list[str] = []
        for lock_file in (self.root / "data").glob("*.lock"):
            lock_file.unlink(missing_ok=True)
            cleaned.append(f"Removed stale lock {lock_file.name}")
        return {"status": "recovered", "actions": cleaned, "crash_count": len(self.list_crashes())}
