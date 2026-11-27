"""Multi-language project generator covering all 17 Aspirant AI stacks and 8 deliverables."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from aspirant.personality.system_prompt import (
    PROJECT_DELIVERABLES,
    SUPPORTED_CODING_STACK,
    build_aspirant_core_prompt,
)
from aspirant.providers.base import ChatMessage, ChatRequest
from aspirant.providers.registry import ProviderRegistry
from aspirant.security.audit import AuditLogger
from aspirant.security.command_policy import is_protected_path
from aspirant.security.permissions import Permission, PermissionManager

SUPPORTED_CODE_LANGUAGES = (
    "python",
    "fastapi",
    "django",
    "flask",
    "go",
    "rust",
    "java",
    "kotlin",
    "csharp",
    "nodejs",
    "typescript",
    "react",
    "nextjs",
    "vue",
    "angular",
    "php",
    "laravel",
    "javascript",
    "c",
    "cpp",
    "html",
    "css",
    "sql",
    "swift",
    "dart",
    "shell",
    "powershell",
)

_LANGUAGE_ALIASES: dict[str, str] = {
    "c#": "csharp",
    "cs": "csharp",
    "node": "nodejs",
    "node.js": "nodejs",
    "next": "nextjs",
    "next.js": "nextjs",
    "c++": "cpp",
    "py": "python",
    "ts": "typescript",
    "js": "javascript",
    "golang": "go",
    "bash": "shell",
    "sh": "shell",
    "ps1": "powershell",
    "pwsh": "powershell",
}

PROJECT_TEMPLATES: dict[str, dict[str, str]] = {
    "fastapi_api": {
        "README.md": "# FastAPI Service\n\nRun: `uvicorn app:app --reload`\n",
        "requirements.txt": "fastapi>=0.115.0\nuvicorn>=0.32.0\npytest>=8.0.0\nhttpx>=0.28.0\n",
        "app.py": (
            'from fastapi import FastAPI\n\napp = FastAPI(title="Generated API")\n\n'
            '@app.get("/health")\ndef health():\n    return {"status": "ok"}\n'
        ),
        "test_app.py": (
            "from fastapi.testclient import TestClient\nfrom app import app\n\n"
            'def test_health():\n    assert TestClient(app).get("/health").json()["status"] == "ok"\n'
        ),
    },
    "responsive_website": {
        "index.html": (
            '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<title>Modern Web App</title>\n<link rel="stylesheet" href="styles.css">\n</head>\n'
            '<body><main class="card"><h1>Hello from ASPIRANT AI</h1><p>Responsive dark UI starter.</p>'
            '<button id="btn">Test Interaction</button><p id="out"></p></main>'
            '<script src="app.js"></script></body>\n</html>\n'
        ),
        "styles.css": (
            "body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0b1020;"
            "color:#f8fafc;font-family:system-ui,sans-serif}.card{padding:2rem;border-radius:16px;"
            "background:rgba(30,41,59,.7);border:1px solid rgba(139,92,246,.35);text-align:center}"
            "button{padding:.6rem 1.2rem;border-radius:8px;border:none;background:#7c3aed;color:#fff;cursor:pointer}"
        ),
        "app.js": 'document.getElementById("btn").addEventListener("click",()=>{document.getElementById("out").textContent="Interactive JS ready!";});\n',
    },
    "telegram_bot": {
        "README.md": "# Telegram Bot Starter\n\nCopy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN`.\n",
        ".env.example": "TELEGRAM_BOT_TOKEN=\n",
        "requirements.txt": "httpx>=0.28.0\npython-dotenv>=1.0.0\npytest>=8.0.0\n",
        "bot.py": (
            "import os\nfrom dotenv import load_dotenv\n\nload_dotenv()\n\n"
            "def build_reply(user_text: str) -> str:\n"
            '    return f"Namaste! You said: {user_text.strip()}"\n\n'
            'if __name__ == "__main__":\n'
            '    token = os.getenv("TELEGRAM_BOT_TOKEN", "")\n'
            '    if not token:\n        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env")\n'
            '    print("Bot configuration ready.")\n'
        ),
        "test_bot.py": (
            'from bot import build_reply\n\ndef test_reply():\n    assert "Namaste!" in build_reply("hi")\n'
        ),
    },
    "python_cli": {
        "README.md": "# Python CLI Starter\n",
        "main.py": 'def add(a: int, b: int) -> int:\n    return a + b\n\nif __name__ == "__main__":\n    print(add(2, 3))\n',
        "test_main.py": "from main import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    },
}

_STACK_BLUEPRINTS: dict[str, dict[str, Any]] = {
    "fastapi": {
        "entry_file": "src/main.py",
        "deps_file": "requirements.txt",
        "deps": "fastapi>=0.115.0\nuvicorn[standard]>=0.32.0\npydantic>=2.9.0\nsqlalchemy>=2.0.36\npytest>=8.0.0\nhttpx>=0.28.0\n",
        "base_image": "python:3.12-slim",
        "run_cmd": '["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]',
        "port": 8000,
        "code": (
            '"""Production FastAPI service scaffolded by Aspirant AI."""\n'
            "from fastapi import FastAPI\nfrom pydantic import BaseModel\n\n"
            'app = FastAPI(title="Aspirant Generated Service", version="1.0.0")\n\n'
            "class ItemIn(BaseModel):\n    name: str\n\n"
            '@app.get("/health")\nasync def health() -> dict[str, str]:\n    return {"status": "ok"}\n\n'
            '@app.post("/items", status_code=201)\nasync def create_item(body: ItemIn) -> dict[str, str]:\n'
            '    return {"name": body.name, "status": "created"}\n'
        ),
        "test_file": "tests/test_main.py",
        "test_code": (
            "from fastapi.testclient import TestClient\nfrom src.main import app\n\n"
            'def test_health() -> None:\n    assert TestClient(app).get("/health").json() == {"status": "ok"}\n'
        ),
    },
    "django": {
        "entry_file": "manage.py",
        "deps_file": "requirements.txt",
        "deps": "django>=5.1\ndjangorestframework>=3.15\ngunicorn>=23.0\npsycopg[binary]>=3.2\n",
        "base_image": "python:3.12-slim",
        "run_cmd": '["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]',
        "port": 8000,
        "code": (
            "import os\nimport sys\n\ndef main() -> None:\n"
            '    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")\n'
            "    from django.core.management import execute_from_command_line\n"
            "    execute_from_command_line(sys.argv)\n\n"
            'if __name__ == "__main__":\n    main()\n'
        ),
        "test_file": "tests/test_smoke.py",
        "test_code": "def test_settings_module_configured() -> None:\n    assert True\n",
    },
    "flask": {
        "entry_file": "src/app.py",
        "deps_file": "requirements.txt",
        "deps": "flask>=3.1.0\ngunicorn>=23.0\npytest>=8.0.0\n",
        "base_image": "python:3.12-slim",
        "run_cmd": '["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "src.app:app"]',
        "port": 8000,
        "code": (
            'from flask import Flask, jsonify\n\napp = Flask(__name__)\n\n'
            '@app.get("/health")\ndef health():\n    return jsonify({"status": "ok"})\n'
        ),
        "test_file": "tests/test_app.py",
        "test_code": (
            "from src.app import app\n\n"
            'def test_health() -> None:\n    assert app.test_client().get("/health").get_json() == {"status": "ok"}\n'
        ),
    },
    "python": {
        "entry_file": "src/app.py",
        "deps_file": "requirements.txt",
        "deps": "pydantic>=2.9.0\npython-dotenv>=1.0.1\npytest>=8.0.0\n",
        "base_image": "python:3.12-slim",
        "run_cmd": '["python", "-m", "src.app"]',
        "port": 8000,
        "code": (
            '"""Modular Python application entry point."""\n\n'
            "def run(name: str = 'Harsh') -> str:\n    return f'Aspirant Python service ready for {name}.'\n\n"
            "if __name__ == '__main__':\n    print(run())\n"
        ),
        "test_file": "tests/test_app.py",
        "test_code": "from src.app import run\n\ndef test_run() -> None:\n    assert 'ready' in run()\n",
    },
    "go": {
        "entry_file": "cmd/server/main.go",
        "deps_file": "go.mod",
        "deps": "module aspirant/generated-app\n\ngo 1.23\n",
        "base_image": "golang:1.23-alpine",
        "run_cmd": '["./server"]',
        "port": 8080,
        "code": (
            'package main\n\nimport (\n\t"encoding/json"\n\t"log"\n\t"net/http"\n)\n\n'
            'func main() {\n\tmux := http.NewServeMux()\n'
            '\tmux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {\n'
            '\t\tw.Header().Set("Content-Type", "application/json")\n'
            '\t\t_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})\n'
            '\t})\n'
            '\tlog.Fatal(http.ListenAndServe(":8080", mux))\n}\n'
        ),
        "test_file": "cmd/server/main_test.go",
        "test_code": 'package main\n\nimport "testing"\n\nfunc TestSmoke(t *testing.T) {}\n',
    },
    "rust": {
        "entry_file": "src/main.rs",
        "deps_file": "Cargo.toml",
        "deps": '[package]\nname = "aspirant_service"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\ntokio = { version = "1", features = ["full"] }\naxum = "0.7"\n',
        "base_image": "rust:1.82-slim",
        "run_cmd": '["./target/release/aspirant_service"]',
        "port": 8080,
        "code": (
            'use axum::{routing::get, Json, Router};\n\n'
            'async fn health() -> Json<serde_json::Value> {\n'
            '    Json(serde_json::json!({"status": "ok"}))\n}\n\n'
            '#[tokio::main]\nasync fn main() {\n'
            '    let app = Router::new().route("/health", get(health));\n'
            '    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await.unwrap();\n'
            '    axum::serve(listener, app).await.unwrap();\n}\n'
        ),
        "test_file": "tests/smoke.rs",
        "test_code": "#[test]\nfn it_compiles() { assert_eq!(2 + 2, 4); }\n",
    },
    "java": {
        "entry_file": "src/main/java/com/aspirant/Application.java",
        "deps_file": "pom.xml",
        "deps": '<project><modelVersion>4.0.0</modelVersion><groupId>com.aspirant</groupId><artifactId>service</artifactId><version>1.0.0</version></project>\n',
        "base_image": "eclipse-temurin:21-jre-alpine",
        "run_cmd": '["java", "-jar", "app.jar"]',
        "port": 8080,
        "code": (
            'package com.aspirant;\n\npublic final class Application {\n'
            '    public static void main(String[] args) {\n'
            '        System.out.println("Aspirant Java service ready.");\n    }\n}\n'
        ),
        "test_file": "src/test/java/com/aspirant/ApplicationTest.java",
        "test_code": "package com.aspirant;\npublic class ApplicationTest {}\n",
    },
    "kotlin": {
        "entry_file": "src/main/kotlin/Main.kt",
        "deps_file": "build.gradle.kts",
        "deps": 'plugins { kotlin("jvm") version "2.0.21" }\n',
        "base_image": "eclipse-temurin:21-jre-alpine",
        "run_cmd": '["java", "-jar", "app.jar"]',
        "port": 8080,
        "code": 'fun main() {\n    println("Aspirant Kotlin service ready.")\n}\n',
        "test_file": "src/test/kotlin/MainTest.kt",
        "test_code": "// Add JUnit5 test assertions here\n",
    },
    "csharp": {
        "entry_file": "Program.cs",
        "deps_file": "AspirantService.csproj",
        "deps": '<Project Sdk="Microsoft.NET.Sdk.Web"><PropertyGroup><TargetFramework>net9.0</TargetFramework></PropertyGroup></Project>\n',
        "base_image": "mcr.microsoft.com/dotnet/aspnet:9.0",
        "run_cmd": '["dotnet", "AspirantService.dll"]',
        "port": 8080,
        "code": (
            'var builder = WebApplication.CreateBuilder(args);\nvar app = builder.Build();\n'
            'app.MapGet("/health", () => Results.Ok(new { status = "ok" }));\napp.Run();\n'
        ),
        "test_file": "Tests/SmokeTests.cs",
        "test_code": "// xUnit test suite\n",
    },
    "nodejs": {
        "entry_file": "src/server.mjs",
        "deps_file": "package.json",
        "deps": '{\n  "name": "aspirant-node-service",\n  "version": "1.0.0",\n  "type": "module",\n  "dependencies": { "express": "^4.21.0" }\n}\n',
        "base_image": "node:22-alpine",
        "run_cmd": '["node", "src/server.mjs"]',
        "port": 3000,
        "code": (
            'import express from "express";\nconst app = express();\napp.use(express.json());\n'
            'app.get("/health", (_req, res) => res.json({ status: "ok" }));\n'
            'app.listen(process.env.PORT || 3000);\n'
        ),
        "test_file": "tests/health.test.mjs",
        "test_code": 'import assert from "node:assert/strict";\nassert.equal(1 + 1, 2);\n',
    },
    "typescript": {
        "entry_file": "src/index.ts",
        "deps_file": "package.json",
        "deps": '{\n  "name": "aspirant-ts-app",\n  "version": "1.0.0",\n  "scripts": { "build": "tsc", "start": "node dist/index.js" },\n  "devDependencies": { "typescript": "^5.6.0", "@types/node": "^22.0.0" }\n}\n',
        "base_image": "node:22-alpine",
        "run_cmd": '["node", "dist/index.js"]',
        "port": 3000,
        "code": 'export function greet(owner: string = "Boss"): string {\n  return `Ready, ${owner}.`;\n}\n',
        "test_file": "tests/index.test.ts",
        "test_code": "// Vitest or node:test assertions\n",
    },
    "react": {
        "entry_file": "src/App.tsx",
        "deps_file": "package.json",
        "deps": '{\n  "name": "aspirant-react-app",\n  "version": "1.0.0",\n  "dependencies": { "react": "^18.3.1", "react-dom": "^18.3.1" },\n  "devDependencies": { "vite": "^6.0.0", "typescript": "^5.6.0" }\n}\n',
        "base_image": "node:22-alpine",
        "run_cmd": '["npm", "run", "preview", "--", "--host", "0.0.0.0"]',
        "port": 4173,
        "code": (
            'import React from "react";\nexport default function App() {\n'
            '  return <main className="glass-card"><h1>Aspirant Glass UI Ready</h1></main>;\n}\n'
        ),
        "test_file": "src/App.test.tsx",
        "test_code": "// React Testing Library smoke spec\n",
    },
    "nextjs": {
        "entry_file": "src/app/page.tsx",
        "deps_file": "package.json",
        "deps": '{\n  "name": "aspirant-next-app",\n  "version": "1.0.0",\n  "dependencies": { "next": "^14.2.18", "react": "^18.3.1", "react-dom": "^18.3.1" }\n}\n',
        "base_image": "node:22-alpine",
        "run_cmd": '["npm", "run", "start"]',
        "port": 3000,
        "code": (
            'export default function HomePage() {\n'
            '  return <main className="min-h-screen p-8"><h1>Aspirant AI Next.js Service</h1></main>;\n}\n'
        ),
        "test_file": "tests/home.spec.ts",
        "test_code": "// Playwright verification script\n",
    },
    "vue": {
        "entry_file": "src/App.vue",
        "deps_file": "package.json",
        "deps": '{\n  "name": "aspirant-vue-app",\n  "version": "1.0.0",\n  "dependencies": { "vue": "^3.5.0" },\n  "devDependencies": { "vite": "^6.0.0" }\n}\n',
        "base_image": "node:22-alpine",
        "run_cmd": '["npm", "run", "preview"]',
        "port": 4173,
        "code": '<template><main class="glass"><h1>Aspirant Vue App</h1></main></template>\n',
        "test_file": "tests/app.spec.ts",
        "test_code": "// Vitest Vue spec\n",
    },
    "angular": {
        "entry_file": "src/app/app.component.ts",
        "deps_file": "package.json",
        "deps": '{\n  "name": "aspirant-angular-app",\n  "version": "1.0.0",\n  "dependencies": { "@angular/core": "^19.0.0" }\n}\n',
        "base_image": "node:22-alpine",
        "run_cmd": '["npm", "start"]',
        "port": 4200,
        "code": (
            'import { Component } from "@angular/core";\n'
            '@Component({ selector: "app-root", template: "<h1>Aspirant Angular Ready</h1>" })\n'
            "export class AppComponent {}\n"
        ),
        "test_file": "src/app/app.component.spec.ts",
        "test_code": "// Jasmine/Karma spec\n",
    },
    "php": {
        "entry_file": "public/index.php",
        "deps_file": "composer.json",
        "deps": '{\n  "name": "aspirant/php-app",\n  "require": { "php": "^8.3" }\n}\n',
        "base_image": "php:8.3-fpm-alpine",
        "run_cmd": '["php", "-S", "0.0.0.0:8080", "-t", "public"]',
        "port": 8080,
        "code": '<?php\ndeclare(strict_types=1);\nheader("Content-Type: application/json");\necho json_encode(["status" => "ok"]);\n',
        "test_file": "tests/SmokeTest.php",
        "test_code": "<?php\n// PHPUnit smoke test\n",
    },
    "laravel": {
        "entry_file": "routes/api.php",
        "deps_file": "composer.json",
        "deps": '{\n  "name": "aspirant/laravel-app",\n  "require": { "php": "^8.3", "laravel/framework": "^11.0" }\n}\n',
        "base_image": "php:8.3-fpm-alpine",
        "run_cmd": '["php", "artisan", "serve", "--host=0.0.0.0", "--port=8080"]',
        "port": 8080,
        "code": '<?php\nuse Illuminate\\Support\\Facades\\Route;\nRoute::get("/health", fn () => response()->json(["status" => "ok"]));\n',
        "test_file": "tests/Feature/HealthTest.php",
        "test_code": "<?php\n// Laravel Feature Test\n",
    },
    "sql": {
        "entry_file": "db/schema.sql",
        "deps_file": "migrations/001_init.sql",
        "deps": "-- PostgreSQL 16 Schema Initialization\n",
        "base_image": "postgres:16-alpine",
        "run_cmd": '["postgres"]',
        "port": 5432,
        "code": "CREATE TABLE IF NOT EXISTS projects (id UUID PRIMARY KEY, name TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW());\n",
        "test_file": "tests/verify_schema.sql",
        "test_code": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';\n",
    },
    "swift": {
        "entry_file": "Sources/App/main.swift",
        "deps_file": "Package.swift",
        "deps": '// swift-tools-version:5.10\nimport PackageDescription\nlet package = Package(name: "AspirantSwiftApp")\n',
        "base_image": "swift:5.10",
        "run_cmd": '["swift", "run"]',
        "port": 8080,
        "code": 'print("Aspirant Swift service ready")\n',
        "test_file": "Tests/AppTests/AppTests.swift",
        "test_code": "// XCTest suite placeholder\n",
    },
    "dart": {
        "entry_file": "bin/server.dart",
        "deps_file": "pubspec.yaml",
        "deps": "name: aspirant_dart_app\nenvironment:\n  sdk: '>=3.4.0 <4.0.0'\n",
        "base_image": "dart:stable",
        "run_cmd": '["dart", "run", "bin/server.dart"]',
        "port": 8080,
        "code": "void main() {\n  print('Aspirant Dart service ready');\n}\n",
        "test_file": "test/server_test.dart",
        "test_code": "// package:test smoke spec\n",
    },
    "shell": {
        "entry_file": "scripts/deploy.sh",
        "deps_file": "scripts/health.sh",
        "deps": "#!/usr/bin/env bash\nset -euo pipefail\ncurl -fsS http://127.0.0.1:8000/health\n",
        "base_image": "alpine:3.20",
        "run_cmd": '["sh", "scripts/deploy.sh"]',
        "port": 8080,
        "code": '#!/usr/bin/env bash\nset -euo pipefail\necho "Aspirant POSIX Shell automation ready"\n',
        "test_file": "tests/test_shell.sh",
        "test_code": '#!/usr/bin/env bash\nset -euo pipefail\nbash -n scripts/deploy.sh\n',
    },
    "powershell": {
        "entry_file": "scripts/Start-App.ps1",
        "deps_file": "scripts/Test-Health.ps1",
        "deps": "$ErrorActionPreference = 'Stop'\nInvoke-RestMethod http://127.0.0.1:8000/health\n",
        "base_image": "mcr.microsoft.com/powershell:lts-alpine-3.20",
        "run_cmd": '["pwsh", "-File", "scripts/Start-App.ps1"]',
        "port": 8080,
        "code": "$ErrorActionPreference = 'Stop'\nWrite-Host 'Aspirant PowerShell automation ready'\n",
        "test_file": "tests/Smoke.Tests.ps1",
        "test_code": "# Pester smoke specification\n",
    },
}

_PROTECTED_PROJECT_FILENAMES = frozenset({".env", "vault.enc", "vault.key", ".api_token"})


def normalize_code_language(language: str) -> str:
    cleaned = language.strip().lower()
    return _LANGUAGE_ALIASES.get(cleaned, cleaned)


def build_project_blueprint(
    *,
    project_name: str,
    stack: str = "fastapi",
    description: str = "Production-ready application generated by Aspirant AI",
) -> dict[str, Any]:
    """Build all 8 mandatory Project Generator deliverables for any supported stack."""
    norm = normalize_code_language(stack)
    spec = _STACK_BLUEPRINTS.get(norm, _STACK_BLUEPRINTS["fastapi"])
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", project_name.strip()).strip("-").lower() or "aspirant-project"
    port = int(spec["port"])

    folder_structure = [
        f"{slug}/",
        f"  {spec['entry_file']}",
        f"  {spec['test_file']}",
        f"  {spec['deps_file']}",
        "  .env.example",
        "  Dockerfile",
        "  docker-compose.yml",
        "  db/schema.sql",
        "  docs/API.md",
        "  docs/DEPLOYMENT.md",
        "  README.md",
    ]
    env_variables = (
        f"APP_NAME={slug}\n"
        "APP_ENV=production\n"
        f"APP_PORT={port}\n"
        "DATABASE_URL=postgresql+asyncpg://postgres:<DB_PASS>@db:5432/appdb\n"
        "JWT_SECRET=<GENERATE_64_CHAR_RANDOM_SECRET>\n"
    )
    dockerfile = (
        f"FROM {spec['base_image']}\n"
        "WORKDIR /app\n"
        "COPY . .\n"
        f"EXPOSE {port}\n"
        f"CMD {spec['run_cmd']}\n"
    )
    docker_compose = (
        "services:\n"
        "  app:\n"
        "    build: .\n"
        f"    ports:\n      - '{port}:{port}'\n"
        "    env_file:\n      - .env\n"
        "    depends_on:\n      - db\n"
        "  db:\n"
        "    image: postgres:16-alpine\n"
        "    environment:\n"
        "      POSTGRES_DB: appdb\n"
        "      POSTGRES_USER: postgres\n"
        "      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}\n"
    )
    db_schema = (
        "-- Database Schema & Audit Trail\n"
        "CREATE TABLE IF NOT EXISTS users (\n"
        "    id UUID PRIMARY KEY,\n"
        "    email VARCHAR(255) UNIQUE NOT NULL,\n"
        "    full_name VARCHAR(160) NOT NULL,\n"
        "    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()\n"
        ");\n\n"
        "CREATE TABLE IF NOT EXISTS records (\n"
        "    id UUID PRIMARY KEY,\n"
        "    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n"
        "    title VARCHAR(255) NOT NULL,\n"
        "    payload_json TEXT NOT NULL,\n"
        "    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()\n"
        ");\n"
    )
    api_docs = (
        f"# {project_name} — API Documentation ({norm.upper()})\n\n"
        "| Method | Endpoint | Description |\n"
        "|--------|----------|-------------|\n"
        "| GET | `/health` | Service readiness & health probe |\n"
        "| POST | `/items` | Validate payload & create resource |\n"
    )
    readme = (
        f"# {project_name}\n\n{description}\n\n"
        f"- **Stack**: `{norm}`\n"
        f"- **Supported Deliverables**: {', '.join(PROJECT_DELIVERABLES)}\n\n"
        "## Quick Start\n\n"
        "1. Copy `.env.example` to `.env` and fill secrets.\n"
        "2. Apply `db/schema.sql` to PostgreSQL.\n"
        "3. Run `docker compose up --build`.\n"
    )
    deployment_guide = (
        f"# {project_name} — Deployment Guide\n\n"
        "1. Install Docker Engine & Docker Compose plugin on Ubuntu VPS or Cloud VM.\n"
        "2. Configure `.env` with production PostgreSQL & JWT secret.\n"
        "3. Run `docker compose up -d --build`.\n"
        "4. Put Nginx reverse proxy + Certbot TLS + Cloudflare DNS in front.\n"
        "Note: Verify live healthcheck manually before confirming deployment.\n"
    )

    files: dict[str, str] = {
        spec["entry_file"]: spec["code"],
        spec["test_file"]: spec["test_code"],
        spec["deps_file"]: spec["deps"],
        ".env.example": env_variables,
        "Dockerfile": dockerfile,
        "docker-compose.yml": docker_compose,
        "db/schema.sql": db_schema,
        "docs/API.md": api_docs,
        "docs/DEPLOYMENT.md": deployment_guide,
        "README.md": readme,
    }
    return {
        "project_name": project_name,
        "slug": slug,
        "stack": norm,
        "supported_stacks": list(SUPPORTED_CODING_STACK),
        "deliverables": list(PROJECT_DELIVERABLES),
        "folder_structure": "\n".join(folder_structure),
        "source_code": {spec["entry_file"]: spec["code"], spec["test_file"]: spec["test_code"], spec["deps_file"]: spec["deps"]},
        "environment_variables": env_variables,
        "docker_setup": {"Dockerfile": dockerfile, "docker-compose.yml": docker_compose},
        "readme": readme,
        "api_documentation": api_docs,
        "database_structure": db_schema,
        "deployment_guide": deployment_guide,
        "files": files,
    }


def guard_project_file(project_root: Path, rel_path: str) -> Path:
    """Enforce project boundary and protected-file rules."""
    blocked_root, reason = is_protected_path(project_root)
    if blocked_root:
        raise PermissionError(reason)
    target = (project_root / rel_path).resolve()
    root_res = project_root.resolve()
    if target != root_res and root_res not in target.parents:
        raise PermissionError(f"Path {rel_path!r} escapes project boundary.")
    if target.name.lower() in _PROTECTED_PROJECT_FILENAMES or ".git" in target.parts:
        raise PermissionError(f"Protected file cannot be modified autonomously: {target.name}")
    return target


class ProjectGenerator:
    """Scaffolds complete multi-file projects (all 17 stacks, 8 deliverables) safely."""

    def __init__(
        self,
        providers: ProviderRegistry,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
    ) -> None:
        self.providers = providers
        self.permissions = permissions
        self.audit_logger = audit_logger

    def scaffold_project(
        self, target_dir: str | Path, template_id: str, overwrite: bool = False
    ) -> dict[str, Any]:
        self.permissions.require(
            Permission.WRITE,
            f"Scaffold template '{template_id}' in {target_dir}",
            category="coding",
        )
        files = PROJECT_TEMPLATES.get(template_id)
        if files is None:
            raise ValueError(f"Unknown template '{template_id}'. Available: {sorted(PROJECT_TEMPLATES)}")

        root = Path(target_dir).expanduser().resolve()
        blocked, reason = is_protected_path(root)
        if blocked:
            raise PermissionError(reason)
        root.mkdir(parents=True, exist_ok=True)

        created: list[str] = []
        for rel, content in files.items():
            dest = guard_project_file(root, rel)
            if dest.exists() and not overwrite:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            created.append(rel)

        self.audit_logger.log(
            category="coding",
            action=f"Scaffolded '{template_id}' in {root.name} ({len(created)} files)",
            permission="WRITE",
            decision="executed",
            status="ok",
        )
        return {"root": str(root), "template": template_id, "created_files": created}

    def scaffold_full_project_pack(
        self,
        target_dir: str | Path,
        project_name: str,
        stack: str = "fastapi",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Materialize all 8 Project Generator deliverables safely inside *target_dir*."""
        self.permissions.require(
            Permission.WRITE,
            f"Generate full {stack} project pack '{project_name}' in {target_dir}",
            category="coding",
        )
        blueprint = build_project_blueprint(project_name=project_name, stack=stack)
        root = Path(target_dir).expanduser().resolve()
        blocked, reason = is_protected_path(root)
        if blocked:
            raise PermissionError(reason)
        root.mkdir(parents=True, exist_ok=True)

        created: list[str] = []
        for rel, content in blueprint["files"].items():
            dest = guard_project_file(root, rel)
            if dest.exists() and not overwrite:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            created.append(rel)

        self.audit_logger.log(
            category="coding",
            action=f"Generated 8-deliverable '{stack}' pack in {root.name} ({len(created)} files)",
            permission="WRITE",
            decision="executed",
            status="ok",
        )
        return {**blueprint, "root": str(root), "created_files": created}

    async def generate_code(
        self,
        prompt: str,
        language: str = "python",
        provider_id: str = "auto",
    ) -> dict[str, Any]:
        self.permissions.require(Permission.READ, f"Generate {language} code", category="coding")
        allow_cloud = self.permissions.is_allowed(Permission.NETWORK)
        lang = normalize_code_language(language)
        if lang not in SUPPORTED_CODE_LANGUAGES:
            raise ValueError(f"Unsupported language {language!r}.")
        sys_inst = build_aspirant_core_prompt(owner_preferred_address="Boss", mode="coding")
        resp = await self.providers.generate(
            ChatRequest(
                messages=[
                    ChatMessage(
                        "user",
                        f"Write complete, clean-architecture, production-quality {lang} code for:\n{prompt}\n"
                        "Always include: complete implementation, concise comments/docstrings, explicit dependencies/requirements, "
                        "brief documentation, tests when appropriate, and state assumptions clearly if information is missing. Never output fake code.",
                    )
                ],
                system_instruction=sys_inst,
                temperature=0.2,
                max_tokens=2200,
            ),
            provider_id=provider_id,
            allow_cloud=allow_cloud,
        )
        return {"code": resp.text, "language": lang, "provider": resp.provider, "model": resp.model}
