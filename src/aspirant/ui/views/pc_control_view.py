"""PC Control Studio: app launcher, inspected terminal, screen vision, isolated Edge, and approvals."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from aspirant.ui.client import AspirantApiClient
from aspirant.ui.theme import PALETTE
from aspirant.ui.widgets.glass import GlassCard, SectionHeader, StatusPill


class PCControlView(QWidget):
    """Permission-gated Windows automation, terminal, screen vision, and browser tab center."""

    def __init__(self, api_client: AspirantApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self._pending_approval_id: str | None = None
        self._pending_command: str = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(14)

        self.header = SectionHeader(
            "PC Control Studio",
            "Permission-gated desktop automation • Command inspection • Isolated Playwright Edge",
            badge_text="GUARDED",
            tone="ok",
        )
        layout.addWidget(self.header)

        # App Launcher & Settings Shortcuts
        apps_card = GlassCard()
        apps_title = QLabel("Allowlisted Applications & Windows Settings")
        apps_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        apps_card.body_layout.addWidget(apps_title)

        app_row = QHBoxLayout()
        for app_id, label in (
            ("edge", "Open Edge"),
            ("vscode", "Open VS Code"),
            ("terminal", "Open Terminal"),
            ("notepad", "Notepad"),
            ("calc", "Calculator"),
            ("explorer", "Explorer"),
        ):
            btn = QPushButton(label)
            btn.setProperty("variant", "ghost")
            btn.clicked.connect(lambda _c, aid=app_id: self._launch_app(aid))
            app_row.addWidget(btn)
        apps_card.body_layout.addLayout(app_row)

        settings_row = QHBoxLayout()
        for pid, label in (
            ("display", "Display Settings"),
            ("sound", "Sound Settings"),
            ("wifi", "Wi-Fi"),
            ("privacy_mic", "Mic Privacy"),
            ("storage", "Storage"),
        ):
            btn = QPushButton(label)
            btn.setProperty("variant", "ghost")
            btn.clicked.connect(lambda _c, s=pid: self._open_settings(s))
            settings_row.addWidget(btn)
        apps_card.body_layout.addLayout(settings_row)
        layout.addWidget(apps_card)

        # Inspected Terminal Runner + Approval Banner
        term_card = GlassCard()
        term_hdr = QHBoxLayout()
        term_title = QLabel("Inspected PowerShell Runner")
        term_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.term_pill = StatusPill("REQUIRES EXECUTE", "info")
        term_hdr.addWidget(term_title)
        term_hdr.addStretch(1)
        term_hdr.addWidget(self.term_pill)
        term_card.body_layout.addLayout(term_hdr)

        cmd_row = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Enter command to inspect & run (e.g. Get-Date, python --version)")
        self.run_cmd_btn = QPushButton("Inspect & Run")
        self.run_cmd_btn.setProperty("variant", "primary")
        self.run_cmd_btn.clicked.connect(self._run_command)
        cmd_row.addWidget(self.cmd_input, 1)
        cmd_row.addWidget(self.run_cmd_btn)
        term_card.body_layout.addLayout(cmd_row)

        self.approval_bar = GlassCard(subtle=True)
        self.approval_bar.setVisible(False)
        ap_row = QHBoxLayout()
        self.approval_lbl = QLabel("Approval required")
        self.approval_lbl.setWordWrap(True)
        approve_btn = QPushButton("Approve & Run")
        approve_btn.setProperty("variant", "primary")
        approve_btn.clicked.connect(self._approve_and_run)
        deny_btn = QPushButton("Deny")
        deny_btn.setProperty("variant", "danger")
        deny_btn.clicked.connect(self._deny_pending)
        ap_row.addWidget(self.approval_lbl, 1)
        ap_row.addWidget(approve_btn)
        ap_row.addWidget(deny_btn)
        self.approval_bar.body_layout.addLayout(ap_row)
        term_card.body_layout.addWidget(self.approval_bar)

        self.term_output = QTextEdit()
        self.term_output.setReadOnly(True)
        self.term_output.setFixedHeight(140)
        self.term_output.setStyleSheet(
            "QTextEdit { background: rgba(10, 14, 28, 0.9); color: #A5F3FC; font-family: Consolas, monospace; border-radius: 8px; padding: 8px; }"
        )
        term_card.body_layout.addWidget(self.term_output)
        layout.addWidget(term_card)

        # Screen Vision + Isolated Edge Tabs
        split_row = QHBoxLayout()

        screen_card = GlassCard()
        s_title = QLabel("Screen Capture & Vision")
        s_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        screen_card.body_layout.addWidget(s_title)
        self.screen_q_input = QLineEdit()
        self.screen_q_input.setPlaceholderText("Ask about visible screen content...")
        s_btns = QHBoxLayout()
        cap_btn = QPushButton("Take Screenshot")
        cap_btn.setProperty("variant", "ghost")
        cap_btn.clicked.connect(self._capture_screen)
        ana_btn = QPushButton("Analyze Screen (Gemini)")
        ana_btn.setProperty("variant", "primary")
        ana_btn.clicked.connect(self._analyze_screen)
        s_btns.addWidget(cap_btn)
        s_btns.addWidget(ana_btn)
        self.screen_out = QLabel("No screenshot captured yet.")
        self.screen_out.setWordWrap(True)
        self.screen_out.setStyleSheet(f"color: {PALETTE['text_secondary']};")
        screen_card.body_layout.addWidget(self.screen_q_input)
        screen_card.body_layout.addLayout(s_btns)
        screen_card.body_layout.addWidget(self.screen_out)

        browser_card = GlassCard()
        b_title = QLabel("Isolated Edge Browser (Playwright)")
        b_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        browser_card.body_layout.addWidget(b_title)
        b_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://services.india.gov.in")
        open_tab_btn = QPushButton("Open Isolated Tab")
        open_tab_btn.setProperty("variant", "primary")
        open_tab_btn.clicked.connect(self._open_browser_tab)
        b_row.addWidget(self.url_input, 1)
        b_row.addWidget(open_tab_btn)
        self.browser_out = QLabel("Uses isolated data/browser_profile (never personal cookies).")
        self.browser_out.setWordWrap(True)
        self.browser_out.setStyleSheet(f"color: {PALETTE['text_secondary']};")
        browser_card.body_layout.addLayout(b_row)
        browser_card.body_layout.addWidget(self.browser_out)

        split_row.addWidget(screen_card, 1)
        split_row.addWidget(browser_card, 1)
        layout.addLayout(split_row)

    def _launch_app(self, app_id: str) -> None:
        try:
            res = self.api_client.open_app(app_id)
            self.term_output.append(f"[APP] Launched {res.get('app')} (PID {res.get('pid')})")
        except Exception as exc:
            self.term_output.append(f"[BLOCKED/ERR] {exc}")

    def _open_settings(self, page_id: str) -> None:
        try:
            res = self.api_client.open_settings_page(page_id)
            self.term_output.append(f"[SETTINGS] Opened {res.get('uri')}")
        except Exception as exc:
            self.term_output.append(f"[BLOCKED/ERR] {exc}")

    def _run_command(self) -> None:
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return
        try:
            res = self.api_client.run_terminal_command(cmd)
            if res.get("status") == "approval_required":
                ap = res["approval"]
                self._pending_approval_id = ap["id"]
                self._pending_command = cmd
                self.approval_lbl.setText(f"Approval required for '{cmd}': {ap['reason']}")
                self.approval_bar.setVisible(True)
                self.term_pill.set_tone("warn", "APPROVAL NEEDED")
                return
            self._render_cmd_result(res)
        except Exception as exc:
            self.term_pill.set_tone("danger", "DENIED")
            self.term_output.append(f"[DENIED] {exc}")

    def _approve_and_run(self) -> None:
        if not self._pending_approval_id:
            return
        try:
            self.api_client.decide_approval(self._pending_approval_id, True)
            res = self.api_client.run_terminal_command(
                self._pending_command, approval_id=self._pending_approval_id
            )
            self.approval_bar.setVisible(False)
            self._pending_approval_id = None
            self._render_cmd_result(res)
        except Exception as exc:
            self.term_output.append(f"[ERROR] {exc}")

    def _deny_pending(self) -> None:
        if self._pending_approval_id:
            try:
                self.api_client.decide_approval(self._pending_approval_id, False)
            except Exception:
                pass
        self._pending_approval_id = None
        self.approval_bar.setVisible(False)
        self.term_pill.set_tone("muted", "DENIED")

    def _render_cmd_result(self, res: dict[str, Any]) -> None:
        rc = res.get("returncode", 0)
        self.term_pill.set_tone("ok" if rc == 0 else "warn", f"EXIT {rc}")
        if res.get("stdout"):
            self.term_output.append(res["stdout"].rstrip())
        if res.get("stderr"):
            self.term_output.append(f"[STDERR] {res['stderr'].rstrip()}")

    def _capture_screen(self) -> None:
        try:
            res = self.api_client.capture_screen()
            self.screen_out.setText(
                f"Saved: {res.get('path')} ({res.get('width')}x{res.get('height')})"
            )
        except Exception as exc:
            self.screen_out.setText(f"Capture failed: {exc}")

    def _analyze_screen(self) -> None:
        try:
            q = self.screen_q_input.text().strip() or "Describe the visible screen clearly."
            res = self.api_client.analyze_screen(q)
            self.screen_out.setText(str(res.get("analysis", "")))
        except Exception as exc:
            self.screen_out.setText(f"Screen vision error: {exc}")

    def _open_browser_tab(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return
        try:
            res = self.api_client.browser_open(url)
            self.browser_out.setText(
                f"Opened: {res.get('title', '')} ({res.get('url', '')}) • Tabs: {res.get('tab_count', 1)}"
            )
        except Exception as exc:
            self.browser_out.setText(f"Browser blocked/error: {exc}")
