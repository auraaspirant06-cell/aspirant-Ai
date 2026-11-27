"""Ecosystem Project Generator (17 stacks, 8 deliverables), DevOps Agent (9 platforms), Debugging & Learning."""

from __future__ import annotations

import re
from typing import Any

from backend.app.ai.system_prompt import (
    PROJECT_DELIVERABLES,
    SUPPORTED_CODING_STACK,
    SUPPORTED_DEVOPS_PLATFORMS,
)


_LANGUAGE_ALIASES = {
    "c#": "csharp",
    "cs": "csharp",
    "node": "nodejs",
    "node.js": "nodejs",
    "next": "nextjs",
    "next.js": "nextjs",
    "py": "python",
    "golang": "go",
}

_STACK_SNIPPETS: dict[str, tuple[str, str, str, int, str]] = {
    "fastapi": ("src/main.py", "requirements.txt", "fastapi>=0.115\nuvicorn>=0.32\npydantic>=2.9\npytest>=8.0\n", 8000, 'from fastapi import FastAPI\napp = FastAPI()\n@app.get("/health")\ndef health():\n    return {"status": "ok"}\n'),
    "django": ("manage.py", "requirements.txt", "django>=5.1\ngunicorn>=23.0\n", 8000, 'import os, sys\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")\n'),
    "flask": ("src/app.py", "requirements.txt", "flask>=3.1\ngunicorn>=23.0\n", 8000, 'from flask import Flask\napp = Flask(__name__)\n@app.get("/health")\ndef health():\n    return {"status": "ok"}\n'),
    "python": ("src/app.py", "requirements.txt", "pydantic>=2.9\npytest>=8.0\n", 8000, 'def main() -> None:\n    print("Aspirant Python service ready")\n'),
    "go": ("cmd/server/main.go", "go.mod", "module aspirant/service\ngo 1.23\n", 8080, 'package main\nfunc main() {}\n'),
    "rust": ("src/main.rs", "Cargo.toml", '[package]\nname = "aspirant_service"\nversion = "0.1.0"\nedition = "2021"\n', 8080, 'fn main() { println!("ok"); }\n'),
    "java": ("src/main/java/App.java", "pom.xml", "<project><modelVersion>4.0.0</modelVersion></project>\n", 8080, "public class App { public static void main(String[] a) {} }\n"),
    "kotlin": ("src/main/kotlin/Main.kt", "build.gradle.kts", 'plugins { kotlin("jvm") version "2.0.21" }\n', 8080, "fun main() {}\n"),
    "csharp": ("Program.cs", "App.csproj", '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>\n', 8080, 'var app = WebApplication.Create(); app.MapGet("/health", () => "ok"); app.Run();\n'),
    "nodejs": ("src/server.mjs", "package.json", '{"name":"node-app","type":"module","dependencies":{"express":"^4.21.0"}}\n', 3000, 'import express from "express";\nconst app = express(); app.listen(3000);\n'),
    "typescript": ("src/index.ts", "package.json", '{"name":"ts-app","devDependencies":{"typescript":"^5.6"}}\n', 3000, 'export const ready = true;\n'),
    "react": ("src/App.tsx", "package.json", '{"name":"react-app","dependencies":{"react":"^18.3.1"}}\n', 4173, 'export default function App(){ return <main>Aspirant Glass UI</main>; }\n'),
    "nextjs": ("src/app/page.tsx", "package.json", '{"name":"next-app","dependencies":{"next":"^14.2.18","react":"^18.3.1"}}\n', 3000, 'export default function Page(){ return <main>Next.js Ready</main>; }\n'),
    "vue": ("src/App.vue", "package.json", '{"name":"vue-app","dependencies":{"vue":"^3.5.0"}}\n', 4173, "<template><main>Vue Ready</main></template>\n"),
    "angular": ("src/app/app.component.ts", "package.json", '{"name":"ng-app","dependencies":{"@angular/core":"^19.0.0"}}\n', 4200, "export class AppComponent {}\n"),
    "php": ("public/index.php", "composer.json", '{"require":{"php":"^8.3"}}\n', 8080, '<?php echo json_encode(["status"=>"ok"]);\n'),
    "laravel": ("routes/api.php", "composer.json", '{"require":{"php":"^8.3","laravel/framework":"^11.0"}}\n', 8080, '<?php Route::get("/health", fn () => ["status"=>"ok"]);\n'),
}


def generate_project_deliverables(
    *,
    project_name: str,
    stack: str = "FastAPI",
    description: str = "Production application scaffold",
) -> dict[str, Any]:
    """Generate all 8 Project Generator deliverables for any supported stack."""
    key = _LANGUAGE_ALIASES.get(stack.strip().lower(), stack.strip().lower())
    entry, deps_file, deps_content, port, code = _STACK_SNIPPETS.get(key, _STACK_SNIPPETS["fastapi"])
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", project_name.strip()).strip("-").lower() or "aspirant-project"
    return {
        "project_name": project_name,
        "stack": key,
        "supported_stacks": list(SUPPORTED_CODING_STACK),
        "deliverables": list(PROJECT_DELIVERABLES),
        "folder_structure": (
            f"{slug}/\n  {entry}\n  {deps_file}\n  .env.example\n  Dockerfile\n"
            "  docker-compose.yml\n  db/schema.sql\n  docs/API.md\n  docs/DEPLOYMENT.md\n  README.md"
        ),
        "source_code": {entry: code, deps_file: deps_content},
        "environment_variables": f"APP_NAME={slug}\nAPP_PORT={port}\nDATABASE_URL=postgresql://postgres:<DB_PASS>@db:5432/appdb\nJWT_SECRET=<SECRET>\n",
        "docker_setup": (
            f"services:\n  {slug}:\n    build: .\n    ports: ['{port}:{port}']\n    env_file: ['.env']\n"
        ),
        "readme": f"# {project_name}\n\n{description}\n\nRun with Docker Compose after setting `.env`.\n",
        "api_documentation": f"# API Documentation ({key.upper()})\n\n- `GET /health` -> 200 `{{\"status\": \"ok\"}}`",
        "database_structure": (
            "CREATE TABLE IF NOT EXISTS users (id UUID PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL);\n"
            "CREATE TABLE IF NOT EXISTS items (id UUID PRIMARY KEY, owner_id UUID REFERENCES users(id));\n"
        ),
        "deployment_guide": (
            "1. Provision host (Docker/Ubuntu VPS/Cloud).\n2. Configure `.env` and database.\n"
            "3. Run `docker compose up -d --build` + Nginx TLS proxy.\n"
            "Status: Pending owner confirmation after live execution."
        ),
    }


def generate_devops_deployment_plan(
    *,
    app_name: str = "aspirant-app",
    platform: str = "Ubuntu VPS",
    domain: str = "app.example.com",
    app_port: int = 8000,
    execution_confirmed: bool = False,
) -> dict[str, Any]:
    """Generate installation, Docker, Nginx reverse proxy, SSL, domain, env, and monitoring plan."""
    plat = next(
        (p for p in SUPPORTED_DEVOPS_PLATFORMS if p.lower() == platform.strip().lower()),
        platform.strip() or "Docker",
    )
    return {
        "platform": plat,
        "supported_platforms": list(SUPPORTED_DEVOPS_PLATFORMS),
        "deployment_executed": execution_confirmed,
        "confirmation_required": not execution_confirmed,
        "status": "completed" if execution_confirmed else "awaiting_user_execution_confirmation",
        "message": (
            f"Confirmed Boss: {app_name} deployment marked complete on {plat}."
            if execution_confirmed
            else f"Understood Boss. Deployment steps prepared for {plat}; awaiting your execution confirmation before marking complete."
        ),
        "installation_commands": [
            "sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx",
            "sudo systemctl enable --now docker nginx",
        ],
        "docker_configuration": (
            f"services:\n  {app_name}:\n    build: .\n    restart: unless-stopped\n"
            f"    ports: ['127.0.0.1:{app_port}:{app_port}']\n    env_file: ['.env']\n"
        ),
        "reverse_proxy_configuration": (
            f"server {{ listen 80; server_name {domain}; "
            f"location / {{ proxy_pass http://127.0.0.1:{app_port}; proxy_set_header Host $host; }} }}"
        ),
        "ssl_setup": f"sudo certbot --nginx -d {domain} --redirect --non-interactive --agree-tos",
        "domain_setup": f"Point DNS A record for {domain} in Cloudflare DNS to server public IP; enable Full (strict) TLS.",
        "environment_setup": "Configure `.env` with `chmod 600 .env`; load `DATABASE_URL` and secrets securely.",
        "monitoring_suggestions": [
            f"Configure HTTP uptime check on https://{domain}/health",
            "Ship container logs + error alerts to Grafana/Loki or cloud monitoring.",
        ],
    }


def analyze_debug_error_log(*, error_log: str, code_context: str = "") -> dict[str, Any]:
    """Structured 5-step debugging analysis: root cause, issue, fix, corrected code, prevention."""
    log = error_log.strip()
    lowered = log.lower()
    if "modulenotfounderror" in lowered or "importerror" in lowered:
        root_cause = "Missing Python dependency or unactivated virtual environment / wrong PYTHONPATH."
        explanation = "The interpreter could not locate the imported module in sys.path or active virtualenv."
        fix = "Install the package inside the project's environment (`uv add <pkg>`) and run from project root."
        corrected = "# Run inside project root with virtualenv active:\n# uv sync && uv run python -m app"
        prevention = ["Pin dependencies in pyproject.toml/requirements.txt", "Run CI smoke imports before deployment"]
    elif "syntaxerror" in lowered or "indentationerror" in lowered:
        root_cause = "Invalid Python/language syntax or inconsistent indentation."
        explanation = "The parser encountered an unclosed bracket, quote, missing colon, or mismatched indent."
        fix = "Inspect the line flagged in the traceback and verify matching delimiters/4-space indentation."
        corrected = code_context or "def example() -> None:\n    pass"
        prevention = ["Enable editor syntax highlighting & ruff/eslint pre-commit checks"]
    elif "connectionrefused" in lowered or "port" in lowered or "eaddrinuse" in lowered:
        root_cause = "Target backend/database port is not listening or is occupied by another process."
        explanation = "The client attempted to connect before the service bound cleanly, or port conflicted."
        fix = "Start the dependent service first, verify health endpoint, or bind an available port."
        corrected = "# Verify listening process & health endpoint before starting client workers"
        prevention = ["Add Docker healthcheck dependencies (`condition: service_healthy`)"]
    elif "keyerror" in lowered or "typeerror" in lowered or "attributeerror" in lowered:
        root_cause = "Unexpected None / missing dictionary key / mismatched type at runtime."
        explanation = "Code accessed an attribute or key directly without validating the payload schema."
        fix = "Use `.get()` defaults, explicit Pydantic validation, and guard None before attribute access."
        corrected = "value = payload.get('key', default_value) if isinstance(payload, dict) else default_value"
        prevention = ["Validate API inputs with Pydantic schemas and add edge-case unit tests for None/missing keys"]
    else:
        root_cause = f"Runtime error reported in log tail: {log.splitlines()[-1][:160] if log else 'Empty log'}"
        explanation = "Analyzed stack trace structure and exception message before proposing changes."
        fix = "Reproduce minimally with a failing unit test, isolate the failing state transition, and apply guardrails."
        corrected = code_context or "# Add defensive validation around the failing call site"
        prevention = ["Add structured logging, typed validation, and regression tests"]

    return {
        "analyzed_first": True,
        "root_cause": root_cause,
        "issue_explanation": explanation,
        "fix": fix,
        "corrected_code": corrected,
        "prevention_methods": prevention,
    }


def build_learning_explanation(*, concept: str, level: str = "beginner-to-intermediate") -> dict[str, Any]:
    """Return Learning Mode scaffold: simple core idea, real-world analogy, example, step-by-step."""
    topic = concept.strip() or "API Routing"
    return {
        "concept": topic,
        "target_level": level,
        "simple_explanation": f"{topic} helps break a complex workflow into predictable, reusable steps.",
        "real_world_analogy": (
            f"Think of {topic} like an organized restaurant kitchen: requests enter cleanly at one counter, "
            "each specialist handles one clear job, and verified dishes go out on time."
        ),
        "example": f"# Practical minimal example illustrating {topic}\ndef run_step(data: str) -> str:\n    return f'Processed {{data}} cleanly'\n",
        "step_by_step": [
            f"1. Understand the problem {topic} solves.",
            "2. Walk through inputs and outputs with one tiny example.",
            "3. Watch out for common beginner pitfalls and add a small test.",
        ],
    }
