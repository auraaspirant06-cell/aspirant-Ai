"""Coding Studio view: project indexer, templates, sandbox tests, Hindi/English explainer, and Git."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from aspirant.coding.generator import PROJECT_TEMPLATES, SUPPORTED_CODE_LANGUAGES
from aspirant.ui.client import AspirantApiClient
from aspirant.ui.widgets.glass import GlassCard, SectionHeader, StatusPill


class CodingStudioView(QWidget):
    """Unified software engineering studio with boundary & approval safeguards."""

    def __init__(self, api_client: AspirantApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self._default_root = str((Path.home() / "Documents" / "AspirantAI").resolve())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        body = QWidget()
        body.setObjectName("ScrollContent")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(12)

        self.header = SectionHeader(
            "Coding Studio",
            "17+ Stacks • 8-Deliverable Project Generator • 9-Platform DevOps • 5-Step Debugger & Learning Mode",
            badge_text="ENGINEER",
            tone="accent",
        )
        layout.addWidget(self.header)

        # Workspace & Project Actions
        proj_card = GlassCard()
        row1 = QHBoxLayout()
        self.project_input = QLineEdit(self._default_root)
        idx_btn = QPushButton("Index Project")
        idx_btn.setProperty("variant", "primary")
        idx_btn.clicked.connect(self._index_project)
        syntax_btn = QPushButton("Check Syntax")
        syntax_btn.setProperty("variant", "ghost")
        syntax_btn.clicked.connect(self._check_syntax)
        test_btn = QPushButton("Run Tests")
        test_btn.setProperty("variant", "ghost")
        test_btn.clicked.connect(self._run_tests)
        docs_btn = QPushButton("Generate Docs")
        docs_btn.setProperty("variant", "ghost")
        docs_btn.clicked.connect(self._gen_docs)
        self.status_pill = StatusPill("READY", "info")
        row1.addWidget(QLabel("Project:"))
        row1.addWidget(self.project_input, 1)
        row1.addWidget(idx_btn)
        row1.addWidget(syntax_btn)
        row1.addWidget(test_btn)
        row1.addWidget(docs_btn)
        row1.addWidget(self.status_pill)
        proj_card.body_layout.addLayout(row1)

        # Scaffold + Git Row
        row2 = QHBoxLayout()
        self.template_combo = QComboBox()
        for tid in PROJECT_TEMPLATES:
            self.template_combo.addItem(tid, tid)
        scaffold_btn = QPushButton("Scaffold Template")
        scaffold_btn.setProperty("variant", "ghost")
        scaffold_btn.clicked.connect(self._scaffold)

        git_status_btn = QPushButton("Git Status")
        git_status_btn.setProperty("variant", "ghost")
        git_status_btn.clicked.connect(self._git_status)

        self.commit_msg = QLineEdit()
        self.commit_msg.setPlaceholderText("Commit message...")
        commit_btn = QPushButton("Commit Changes")
        commit_btn.setProperty("variant", "ghost")
        commit_btn.clicked.connect(self._git_commit)

        review_btn = QPushButton("Pre-Deploy Review")
        review_btn.setProperty("variant", "ghost")
        review_btn.clicked.connect(self._git_review)

        row2.addWidget(self.template_combo)
        row2.addWidget(scaffold_btn)
        row2.addWidget(git_status_btn)
        row2.addWidget(self.commit_msg, 1)
        row2.addWidget(commit_btn)
        row2.addWidget(review_btn)
        proj_card.body_layout.addLayout(row2)
        layout.addWidget(proj_card)

        # Code Generator & Bilingual Explainer
        ai_card = GlassCard()
        ai_top = QHBoxLayout()
        self.lang_combo = QComboBox()
        for lang in SUPPORTED_CODE_LANGUAGES:
            self.lang_combo.addItem(lang.upper(), lang)
        self.explain_lang_combo = QComboBox()
        self.explain_lang_combo.addItem("Explain in Hinglish", "hinglish")
        self.explain_lang_combo.addItem("Explain in Hindi", "hi")
        self.explain_lang_combo.addItem("Explain in English", "en")
        gen_btn = QPushButton("Generate Code")
        gen_btn.setProperty("variant", "primary")
        gen_btn.clicked.connect(self._generate_code)
        pack_btn = QPushButton("8-File Project Pack")
        pack_btn.setProperty("variant", "ghost")
        pack_btn.clicked.connect(self._generate_project_pack)
        devops_btn = QPushButton("DevOps Plan")
        devops_btn.setProperty("variant", "ghost")
        devops_btn.clicked.connect(self._generate_devops_plan)
        debug_btn = QPushButton("Debug Log")
        debug_btn.setProperty("variant", "ghost")
        debug_btn.clicked.connect(self._debug_log)
        exp_btn = QPushButton("Explain Code")
        exp_btn.setProperty("variant", "ghost")
        exp_btn.clicked.connect(self._explain_code)
        ai_top.addWidget(QLabel("Language:"))
        ai_top.addWidget(self.lang_combo)
        ai_top.addWidget(self.explain_lang_combo)
        ai_top.addStretch(1)
        ai_top.addWidget(gen_btn)
        ai_top.addWidget(pack_btn)
        ai_top.addWidget(devops_btn)
        ai_top.addWidget(debug_btn)
        ai_top.addWidget(exp_btn)
        ai_card.body_layout.addLayout(ai_top)

        self.code_editor = QTextEdit()
        self.code_editor.setFixedHeight(160)
        self.code_editor.setPlaceholderText("Describe code to generate OR paste code here to explain in Hindi/English/Hinglish...")
        self.code_editor.setStyleSheet(
            "QTextEdit { background: rgba(10, 14, 28, 0.88); color: #F8FAFC; font-family: Consolas, monospace; border-radius: 8px; padding: 8px; }"
        )
        ai_card.body_layout.addWidget(self.code_editor)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setMinimumHeight(190)
        self.output_box.setStyleSheet(
            "QTextEdit { background: rgba(8, 12, 24, 0.92); color: #A5F3FC; font-family: Consolas, monospace; border-radius: 8px; padding: 8px; }"
        )
        ai_card.body_layout.addWidget(self.output_box)
        layout.addWidget(ai_card)

    def _root(self) -> str:
        return self.project_input.text().strip()

    def _show(self, text: str, tone: str = "ok", badge: str = "DONE") -> None:
        self.status_pill.set_tone(tone, badge)
        self.output_box.setPlainText(text)

    def _index_project(self) -> None:
        try:
            res = self.api_client._request("POST", "/api/v1/coding/index", json={"project_root": self._root()})
            lines = [
                f"Project: {res['name']} ({res['primary_language']})",
                f"Files: {res['file_count']} | Tests: {res['has_tests']} | Manifests: {res['manifests']}",
                f"Languages: {res['language_breakdown']}",
                "--- Sample Files ---",
            ]
            for f in res["files"][:30]:
                lines.append(f"  {f['path']} [{f['language']}] {f['symbols'][:4]}")
            self._show("\n".join(lines), "ok", "INDEXED")
        except Exception as exc:
            self._show(str(exc), "danger", "ERROR")

    def _check_syntax(self) -> None:
        try:
            res = self.api_client._request("POST", "/api/v1/coding/syntax", json={"project_root": self._root()})
            self._show(f"Syntax OK: {res['ok']} (Checked {res['checked_files']} Python files)\nIssues: {res['issues']}")
        except Exception as exc:
            self._show(str(exc), "danger", "ERROR")

    def _run_tests(self) -> None:
        try:
            res = self.api_client._request("POST", "/api/v1/coding/tests", json={"project_root": self._root()}, timeout=50.0)
            self._show(
                f"Command: {res['command']}\nPassed: {res['passed']} (exit={res['returncode']})\n\n"
                f"{res['stdout']}\n{res['stderr']}\nParsed Errors: {res['parsed_errors']}",
                "ok" if res["passed"] else "warn",
                "PASSED" if res["passed"] else "FAILED",
            )
        except Exception as exc:
            self._show(str(exc), "danger", "BLOCKED")

    def _gen_docs(self) -> None:
        try:
            res = self.api_client._request("POST", "/api/v1/coding/docs", json={"project_root": self._root()})
            self._show(res["markdown"], "ok", "DOCS READY")
        except Exception as exc:
            self._show(str(exc), "danger", "ERROR")

    def _scaffold(self) -> None:
        try:
            tid = str(self.template_combo.currentData())
            res = self.api_client._request(
                "POST", "/api/v1/coding/scaffold", json={"target_dir": self._root(), "template_id": tid}
            )
            self._show(f"Scaffolded '{tid}' in {res['root']}\nCreated: {res['created_files']}")
        except Exception as exc:
            self._show(str(exc), "danger", "WRITE NEEDED")

    def _git_status(self) -> None:
        try:
            res = self.api_client._request("POST", "/api/v1/coding/git/status", json={"project_root": self._root()})
            self._show(str(res))
        except Exception as exc:
            self._show(str(exc), "danger", "ERROR")

    def _git_commit(self) -> None:
        msg = self.commit_msg.text().strip()
        if not msg:
            self._show("Enter a commit message first.", "warn", "MSG NEEDED")
            return
        try:
            res = self.api_client._request(
                "POST", "/api/v1/coding/git/commit", json={"project_root": self._root(), "message": msg}
            )
            self._show(f"Committed {res['commit_sha']} ({res['files_staged']} files): {res['message']}")
        except Exception as exc:
            self._show(str(exc), "danger", "WRITE NEEDED")

    def _git_review(self) -> None:
        try:
            res = self.api_client._request("POST", "/api/v1/coding/git/review", json={"project_root": self._root()})
            self._show(f"Pre-Deploy Ready: {res['ready']}\nFindings: {res['findings']}\nGit: {res['git']}")
        except Exception as exc:
            self._show(str(exc), "danger", "ERROR")

    def _generate_code(self) -> None:
        prompt = self.code_editor.toPlainText().strip()
        if not prompt:
            return
        try:
            res = self.api_client._request(
                "POST",
                "/api/v1/coding/generate",
                json={"prompt": prompt, "language": str(self.lang_combo.currentData())},
                timeout=45.0,
            )
            self._show(res["code"], "ok", res["language"].upper())
        except Exception as exc:
            self._show(str(exc), "warn", "PROVIDER")

    def _explain_code(self) -> None:
        code = self.code_editor.toPlainText().strip()
        if not code:
            return
        try:
            res = self.api_client._request(
                "POST",
                "/api/v1/coding/explain",
                json={"code": code, "language_mode": str(self.explain_lang_combo.currentData())},
                timeout=45.0,
            )
            self._show(res["explanation"], "ok", res["language"].upper())
        except Exception as exc:
            self._show(str(exc), "warn", "ERROR")

    def _generate_project_pack(self) -> None:
        stack = str(self.lang_combo.currentData() or "fastapi")
        name = Path(self._root()).name or "aspirant-service"
        try:
            res = self.api_client._request(
                "POST",
                "/api/v1/coding/project-pack",
                json={"project_name": name, "stack": stack},
            )
            self._show(
                f"Deliverables ({len(res['deliverables'])}): {', '.join(res['deliverables'])}\n\n"
                f"Folder Structure:\n{res['folder_structure']}\n\nAPI Docs:\n{res['api_documentation']}\n\nDB Schema:\n{res['database_structure']}",
                "ok",
                stack.upper(),
            )
        except Exception as exc:
            self._show(str(exc), "warn", "ERROR")

    def _generate_devops_plan(self) -> None:
        name = Path(self._root()).name or "aspirant-app"
        try:
            res = self.api_client._request(
                "POST",
                "/api/v1/coding/deploy-guide",
                json={"app_name": name, "platform": "Ubuntu VPS", "execution_confirmed": False},
            )
            self._show(
                f"Status: {res['status']} (Confirmed: {res['deployment_executed']})\n"
                f"{res['message']}\n\nNginx:\n{res['reverse_proxy_configuration']}\n\nSSL:\n{res['ssl_setup']}",
                "ok",
                "DEVOPS READY",
            )
        except Exception as exc:
            self._show(str(exc), "warn", "ERROR")

    def _debug_log(self) -> None:
        log = self.code_editor.toPlainText().strip()
        if not log:
            self._show("Paste an error log / traceback above to analyze root cause.", "warn", "INPUT")
            return
        try:
            res = self.api_client._request(
                "POST",
                "/api/v1/coding/debug",
                json={"error_log": log},
            )
            self._show(
                f"Root Cause: {res['root_cause']}\nIssue: {res['issue_explanation']}\nFix: {res['fix']}\n\n"
                f"Prevention:\n- " + "\n- ".join(res["prevention_methods"]),
                "ok",
                "DIAGNOSED",
            )
        except Exception as exc:
            self._show(str(exc), "warn", "ERROR")
