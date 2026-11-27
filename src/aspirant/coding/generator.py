"""Multi-language project generator (APIs, Websites, Telegram Bots, Polyglot templates)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aspirant.providers.base import ChatMessage, ChatRequest
from aspirant.providers.registry import ProviderRegistry
from aspirant.security.audit import AuditLogger
from aspirant.security.command_policy import is_protected_path
from aspirant.security.permissions import Permission, PermissionManager

SUPPORTED_CODE_LANGUAGES = (
    "python",
    "javascript",
    "typescript",
    "go",
    "java",
    "c",
    "cpp",
    "html",
    "css",
)

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

_PROTECTED_PROJECT_FILENAMES = frozenset({".env", "vault.enc", "vault.key", ".api_token"})


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
    """Scaffolds complete multi-file projects and generates/refactors code safely."""

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
        self.permissions.require(Permission.WRITE, f"Scaffold template '{template_id}' in {target_dir}", category="coding")
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

    async def generate_code(
        self,
        prompt: str,
        language: str = "python",
        provider_id: str = "auto",
    ) -> dict[str, Any]:
        self.permissions.require(Permission.READ, f"Generate {language} code", category="coding")
        allow_cloud = self.permissions.is_allowed(Permission.NETWORK)
        lang = language.lower()
        if lang not in SUPPORTED_CODE_LANGUAGES:
            raise ValueError(f"Unsupported language {language!r}.")
        resp = await self.providers.generate(
            ChatRequest(
                messages=[
                    ChatMessage(
                        "user",
                        f"Write clean, production-quality {lang} code for:\n{prompt}\n"
                        "Include concise docstrings/comments and zero placeholder secrets.",
                    )
                ],
                system_instruction="You are ASPIRANT AI Coding Expert.",
                temperature=0.2,
                max_tokens=1800,
            ),
            provider_id=provider_id,
            allow_cloud=allow_cloud,
        )
        return {"code": resp.text, "language": lang, "provider": resp.provider, "model": resp.model}
