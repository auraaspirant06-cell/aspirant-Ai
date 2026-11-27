"""Connected AI Models, Settings, and honest Phase-Readiness module views."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aspirant.ui.theme import PALETTE
from aspirant.ui.widgets.glass import GlassCard, SectionHeader, StatusPill


class ModelsView(QWidget):
    """Displays connected AI models, health checks, encrypted key configuration, and usage."""

    def __init__(
        self,
        on_health_check: Callable[[], None] | None = None,
        on_save_key: Callable[[str, str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_health_check = on_health_check
        self._on_save_key = on_save_key
        self._cached_health: dict[str, dict[str, Any]] = {}

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
            "Connected AI Models",
            "Multi-provider AI registry • DPAPI-encrypted vault & live health telemetry",
            badge_text="GEMINI PRIMARY",
            tone="accent",
        )
        layout.addWidget(self.header)

        # Encrypted Key Configuration Form
        config_card = GlassCard()
        cfg_top = QHBoxLayout()
        cfg_title = QLabel("Configure Provider Credential (Stored Encrypted in vault.enc)")
        cfg_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        self.health_btn = QPushButton("Run Provider Health Checks")
        self.health_btn.setProperty("variant", "primary")
        self.health_btn.clicked.connect(self._handle_health_click)
        cfg_top.addWidget(cfg_title)
        cfg_top.addStretch(1)
        cfg_top.addWidget(self.health_btn)
        config_card.body_layout.addLayout(cfg_top)

        form_row = QHBoxLayout()
        self.key_selector = QComboBox()
        self.key_selector.addItems(
            [
                "GEMINI_API_KEY",
                "OPENAI_API_KEY",
                "OPENAI_BASE_URL",
                "GROQ_API_KEY",
                "OLLAMA_BASE_URL",
                "ELEVENLABS_API_KEY",
            ]
        )
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("Paste API key or endpoint URL (never logged or returned)")
        self.save_key_btn = QPushButton("Save Encrypted")
        self.save_key_btn.setProperty("variant", "ghost")
        self.save_key_btn.clicked.connect(self._handle_save_key)
        form_row.addWidget(self.key_selector)
        form_row.addWidget(self.key_input, 1)
        form_row.addWidget(self.save_key_btn)
        config_card.body_layout.addLayout(form_row)

        self.config_feedback = QLabel("API keys are encrypted with Windows DPAPI + AES before saving.")
        self.config_feedback.setStyleSheet(f"color: {PALETTE['text_muted']}; font-size: 11px;")
        config_card.body_layout.addWidget(self.config_feedback)
        layout.addWidget(config_card)

        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(12)
        layout.addLayout(self.cards_grid)

        # Usage Ledger
        usage_card = GlassCard()
        u_title = QLabel("Provider Token & Cost Ledger")
        u_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        usage_card.body_layout.addWidget(u_title)
        self.usage_table = QTableWidget(0, 6)
        self.usage_table.setHorizontalHeaderLabels(
            ["Provider", "Model", "Calls", "Input Tok", "Output Tok", "Est. Cost (USD)"]
        )
        self.usage_table.verticalHeader().setVisible(False)
        self.usage_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.usage_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.usage_table.setMinimumHeight(140)
        usage_card.body_layout.addWidget(self.usage_table)
        layout.addWidget(usage_card)

    def _handle_health_click(self) -> None:
        if self._on_health_check:
            self.config_feedback.setText("Running live provider health checks...")
            self._on_health_check()

    def _handle_save_key(self) -> None:
        val = self.key_input.text().strip()
        key_name = self.key_selector.currentText()
        if self._on_save_key:
            self._on_save_key(key_name, val)
            self.key_input.clear()
            self.config_feedback.setText(f"Saved {key_name} encrypted to vault.enc and reloaded registry.")

    def update_providers(self, providers: list[dict[str, Any]]) -> None:
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for idx, prov in enumerate(providers):
            pid = str(prov.get("id", ""))
            merged = dict(prov)
            if "healthy" not in merged and pid in self._cached_health:
                cached = self._cached_health[pid]
                if bool(cached.get("configured")) == bool(merged.get("configured")):
                    merged["healthy"] = cached.get("healthy")
                    merged["latency_ms"] = cached.get("latency_ms", 0)
                    merged["detail"] = cached.get("detail", merged.get("detail"))

            card = GlassCard()
            top = QHBoxLayout()
            title = QLabel(str(merged.get("name", "")))
            title.setStyleSheet("font-size: 15px; font-weight: 700;")
            configured = bool(merged.get("configured", False))
            healthy = merged.get("healthy")
            if healthy is True:
                pill = StatusPill(f"HEALTHY ({merged.get('latency_ms', 0)} ms)", "ok")
            elif healthy is False and configured:
                pill = StatusPill("UNREACHABLE", "danger")
            elif configured:
                pill = StatusPill("CONFIGURED", "ok")
            else:
                pill = StatusPill("API KEY REQUIRED", "warn")
            top.addWidget(title)
            top.addStretch(1)
            top.addWidget(pill)

            detail_txt = str(merged.get("detail") or merged.get("role") or "")
            role_lbl = QLabel(detail_txt)
            role_lbl.setWordWrap(True)
            role_lbl.setStyleSheet(f"color: {PALETTE['text_secondary']};")

            mode_lbl = QLabel(f"Mode: {str(merged.get('mode', '')).upper()}")
            mode_lbl.setProperty("role", "mono")

            card.body_layout.addLayout(top)
            card.body_layout.addWidget(role_lbl)
            card.body_layout.addWidget(mode_lbl)
            self.cards_grid.addWidget(card, idx // 2, idx % 2)

    def update_health_and_usage(self, health_items: list[dict[str, Any]], usage_items: list[dict[str, Any]]) -> None:
        self._cached_health = {str(item.get("id", "")): item for item in health_items}
        self.update_providers(health_items)
        self.config_feedback.setText("Health checks completed.")
        self.usage_table.setRowCount(len(usage_items))
        for r, item in enumerate(usage_items):
            self.usage_table.setItem(r, 0, QTableWidgetItem(str(item.get("provider", ""))))
            self.usage_table.setItem(r, 1, QTableWidgetItem(str(item.get("model", ""))))
            self.usage_table.setItem(r, 2, QTableWidgetItem(str(item.get("calls", 0))))
            self.usage_table.setItem(r, 3, QTableWidgetItem(str(item.get("total_input_tokens", 0))))
            self.usage_table.setItem(r, 4, QTableWidgetItem(str(item.get("total_output_tokens", 0))))
            self.usage_table.setItem(r, 5, QTableWidgetItem(f"${item.get('total_estimated_cost_usd', 0):.6f}"))


class SettingsView(QWidget):
    """Displays live system configuration, hardware profile, and 9-phase roadmap status."""

    PHASES = [
        ("Phase 1", "Core Application & Desktop UI", "COMPLETED", "ok"),
        ("Phase 2", "AI Chat & 18+ Indian Languages", "COMPLETED", "ok"),
        ("Phase 3", "Female Voice Assistant & Wake Word", "COMPLETED", "ok"),
        ("Phase 4", "Secure PC Automation & Playwright", "COMPLETED", "ok"),
        ("Phase 5", "Advanced Coding Agent Studio", "COMPLETED", "ok"),
        ("Phase 6", "Indian Government Online Services", "COMPLETED", "ok"),
        ("Phase 7", "Image & AI Video Generation Studio", "COMPLETED", "ok"),
        ("Phase 8", "Encrypted Vault, Memory & Optimization", "COMPLETED", "ok"),
        ("Phase 9", "Full Regression Suite & Packaging", "COMPLETED", "ok"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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

        layout.addWidget(
            SectionHeader(
                "Settings & Environment",
                "Local runtime configuration, RAM budget guardrails, and build roadmap",
                badge_text="PRODUCTION READY",
                tone="ok",
            )
        )

        self.runtime_card = GlassCard()
        rt_title = QLabel("Active Runtime Configuration")
        rt_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.runtime_card.body_layout.addWidget(rt_title)
        self.runtime_details = QLabel("Loading runtime configuration...")
        self.runtime_details.setWordWrap(True)
        self.runtime_details.setProperty("role", "mono")
        self.runtime_card.body_layout.addWidget(self.runtime_details)
        layout.addWidget(self.runtime_card)

        roadmap_card = GlassCard()
        rm_title = QLabel("Modular Build Tracker (No Fake Modules)")
        rm_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        roadmap_card.body_layout.addWidget(rm_title)

        for phase, desc, status_txt, tone in self.PHASES:
            row_card = GlassCard(subtle=True)
            row = QHBoxLayout()
            lbl = QLabel(f"{phase}: {desc}")
            lbl.setStyleSheet("font-weight: 600;")
            row.addWidget(lbl)
            row.addStretch(1)
            row.addWidget(StatusPill(status_txt, tone))
            row_card.body_layout.addLayout(row)
            roadmap_card.body_layout.addWidget(row_card)

        layout.addWidget(roadmap_card)
        layout.addStretch(1)

    def update_overview(self, overview: dict[str, Any]) -> None:
        tel = overview.get("telemetry", {})
        self.runtime_details.setText(
            f"Version       : {overview.get('version', '0.1.0')}\n"
            f"Data Directory: {overview.get('data_dir', '')}\n"
            f"RAM Budget    : <= {overview.get('ram_budget_mb', 320)} MB idle "
            f"(Current: {tel.get('app_ram_mb', 0)} MB)\n"
            f"Host Memory   : {tel.get('ram_available_mb', 0)} MB free / {tel.get('ram_total_mb', 0)} MB total\n"
            f"Disk C:\\ Free : {tel.get('disk_free_gb', 0)} GB"
        )
