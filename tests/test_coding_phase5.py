"""Phase 5 tests for project indexing, templates, sandboxed tests, Git (dulwich), explainer, and autonomous loop."""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncIterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fastapi.testclient import TestClient
from PySide6.QtWidgets import QApplication
import pytest

from aspirant.coding.generator import guard_project_file
from aspirant.coding.sandbox import parse_terminal_errors
from aspirant.core.config import AppSettings
from aspirant.providers.base import ChatRequest, ChatResponse, LLMProvider, ProviderHealth, StreamChunk
from aspirant.server.app import build_container, create_app
from aspirant.ui.views.coding_view import CodingStudioView


class _MockCoderLLM(LLMProvider):
    provider_id = "gemini"
    display_name = "Mock Coder Gemini"
    default_model = "gemini-4-argon"
    mode = "cloud"

    def is_configured(self) -> bool:
        return True

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(self.provider_id, self.display_name, True, True)

    async def generate(self, request: ChatRequest) -> ChatResponse:
        if "Test failures" in request.messages[-1].content:
            return ChatResponse(
                text="def add(a: int, b: int) -> int:\n    return a + b",
                provider=self.provider_id,
                model=self.default_model,
            )
        return ChatResponse(
            text="Yah Python function do numbers ko add karta hai.",
            provider=self.provider_id,
            model=self.default_model,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(delta_text="ok", done=True)


def test_project_boundary_and_error_parser(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    with pytest.raises(PermissionError):
        guard_project_file(proj, "../outside.py")
    with pytest.raises(PermissionError):
        guard_project_file(proj, ".env")

    trace = '  File "app.py", line 12, in <module>\nAssertionError: 4 != 5'
    errs = parse_terminal_errors(trace)
    assert len(errs) == 1
    assert errs[0]["line"] == 12
    assert errs[0]["error_type"] == "AssertionError"


def test_coding_studio_scaffold_test_git_and_autonomous_fix(tmp_path: Path) -> None:
    settings = AppSettings(ASPIRANT_DATA_DIR=tmp_path / "data")
    container = build_container(settings)
    container.providers.register(_MockCoderLLM())
    app = create_app(settings=settings, container=container)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {container.api_token}"}

    proj_dir = tmp_path / "mini_api"
    with client:
        client.post("/api/v1/system/permissions", headers=headers, json={"permission": "WRITE", "granted": True})
        client.post("/api/v1/system/permissions", headers=headers, json={"permission": "EXECUTE", "granted": True})

        # 1. Scaffold Python CLI & run passing pytest
        sc = client.post(
            "/api/v1/coding/scaffold",
            headers=headers,
            json={"target_dir": str(proj_dir), "template_id": "python_cli"},
        )
        assert sc.status_code == 200
        assert "main.py" in sc.json()["created_files"]

        idx = client.post("/api/v1/coding/index", headers=headers, json={"project_root": str(proj_dir)})
        assert idx.status_code == 200
        assert idx.json()["primary_language"] == "Python"
        assert idx.json()["has_tests"] is True

        syntax = client.post("/api/v1/coding/syntax", headers=headers, json={"project_root": str(proj_dir)})
        assert syntax.status_code == 200
        assert syntax.json()["ok"] is True

        tests = client.post("/api/v1/coding/tests", headers=headers, json={"project_root": str(proj_dir)})
        assert tests.status_code == 200
        assert tests.json()["passed"] is True

        # 2. Git init, branch, commit & pre-deploy review via dulwich (no git.exe required)
        assert client.post("/api/v1/coding/git/init", headers=headers, json={"project_root": str(proj_dir)}).status_code == 200
        cm = client.post(
            "/api/v1/coding/git/commit",
            headers=headers,
            json={"project_root": str(proj_dir), "message": "Initial commit"},
        )
        assert cm.status_code == 200
        assert len(cm.json()["commit_sha"]) >= 7

        br = client.post(
            "/api/v1/coding/git/branch",
            headers=headers,
            json={"project_root": str(proj_dir), "branch_name": "feature/tests"},
        )
        assert br.status_code == 200
        st = client.post("/api/v1/coding/git/status", headers=headers, json={"project_root": str(proj_dir)})
        assert st.json()["branch"] == "feature/tests"

        rev = client.post("/api/v1/coding/git/review", headers=headers, json={"project_root": str(proj_dir)})
        assert rev.status_code == 200
        assert rev.json()["ready"] is True

        # 3. Deliberate bug fixed autonomously after explicit approval
        (proj_dir / "main.py").write_text("def add(a: int, b: int) -> int:\n    return a - b\n", encoding="utf-8")
        req_ap = client.post(
            "/api/v1/coding/autonomous",
            headers=headers,
            json={"project_root": str(proj_dir), "goal": "Fix add()", "target_file": "main.py"},
        )
        assert req_ap.json()["status"] == "approval_required"
        ap_id = req_ap.json()["approval"]["id"]
        client.post(f"/api/v1/approvals/{ap_id}", headers=headers, json={"approve": True})

        fixed = client.post(
            "/api/v1/coding/autonomous",
            headers=headers,
            json={"project_root": str(proj_dir), "goal": "Fix add()", "target_file": "main.py", "approval_id": ap_id},
        )
        assert fixed.status_code == 200
        assert fixed.json()["status"] == "completed"

        # 4. Bilingual explanation & docs
        exp = client.post(
            "/api/v1/coding/explain",
            headers=headers,
            json={"code": "def add(a, b): return a + b", "language_mode": "hinglish"},
        )
        assert exp.status_code == 200
        assert "explanation" in exp.json()

        docs = client.post("/api/v1/coding/docs", headers=headers, json={"project_root": str(proj_dir)})
        assert docs.status_code == 200
        assert "# mini_api" in docs.json()["markdown"]

    qt = QApplication.instance() or QApplication([])
    ui = CodingStudioView(api_client=None)  # type: ignore[arg-type]
    assert ui.template_combo.count() == 4
    assert ui.lang_combo.count() >= 17
    qt.processEvents()


def test_aspirant_prompt_project_generator_devops_debug_and_learning(tmp_path: Path) -> None:
    from aspirant.coding.devops import build_deployment_guide
    from aspirant.coding.generator import (
        SUPPORTED_CODE_LANGUAGES,
        build_project_blueprint,
        normalize_code_language,
    )
    from aspirant.coding.sandbox import analyze_error_log
    from aspirant.personality.system_prompt import (
        OWNER_NAMES,
        PROJECT_DELIVERABLES,
        SUPPORTED_CODING_STACK,
        SUPPORTED_DEVOPS_PLATFORMS,
        build_aspirant_core_prompt,
        detect_interaction_mode,
    )

    assert "Harsh" in OWNER_NAMES and "Boss" in OWNER_NAMES
    assert len(SUPPORTED_CODING_STACK) == 17
    assert len(PROJECT_DELIVERABLES) == 8
    assert len(SUPPORTED_DEVOPS_PLATFORMS) == 9
    assert normalize_code_language("C#") == "csharp"
    assert normalize_code_language("Next.js") == "nextjs"
    assert "rust" in SUPPORTED_CODE_LANGUAGES and "laravel" in SUPPORTED_CODE_LANGUAGES

    prompt = build_aspirant_core_prompt(mode="devops")
    assert "Aspirant AI" in prompt
    assert "Never pretend an action succeeded" in prompt
    assert "Do not claim deployment is complete unless the owner confirms execution" in prompt

    assert detect_interaction_mode("Traceback (most recent call last): ModuleNotFoundError") == "debugging"
    assert detect_interaction_mode("Deploy this Docker app to AWS behind Nginx") == "devops"
    assert detect_interaction_mode("Create a FastAPI backend project") == "project_generator"
    assert detect_interaction_mode("Explain Kubernetes step by step with analogy") == "learning"

    bp = build_project_blueprint(project_name="Demo App", stack="FastAPI")
    assert len(bp["deliverables"]) == 8
    assert "Dockerfile" in bp["files"] and "db/schema.sql" in bp["files"] and "docs/DEPLOYMENT.md" in bp["files"]

    dep = build_deployment_guide(app_name="demo", platform="Ubuntu VPS", execution_confirmed=False)
    assert dep["deployment_executed"] is False and dep["confirmation_required"] is True

    dbg = analyze_error_log("Traceback:\n  File \"main.py\", line 4\nModuleNotFoundError: No module named 'fastapi'")
    assert dbg["analyzed_first"] is True and "ModuleNotFoundError" in dbg["root_cause"]

    settings = AppSettings(ASPIRANT_DATA_DIR=tmp_path / "data")
    container = build_container(settings)
    app = create_app(settings=settings, container=container)
    headers = {"Authorization": f"Bearer {container.api_token}"}
    with TestClient(app) as client:
        p = client.post("/api/v1/coding/project-pack", headers=headers, json={"project_name": "Demo", "stack": "Go"})
        assert p.status_code == 200 and p.json()["stack"] == "go" and len(p.json()["deliverables"]) == 8
        d = client.post("/api/v1/coding/deploy-guide", headers=headers, json={"platform": "Cloudflare", "execution_confirmed": False})
        assert d.status_code == 200 and d.json()["confirmation_required"] is True
        b = client.post("/api/v1/coding/debug", headers=headers, json={"error_log": "SyntaxError: invalid syntax"})
        assert b.status_code == 200 and b.json()["analyzed_first"] is True
        l = client.post("/api/v1/coding/learn", headers=headers, json={"concept": "REST APIs"})
        assert l.status_code == 200 and l.json()["concept"] == "REST APIs"
