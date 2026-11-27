"""Home Dashboard view with live telemetry, providers, permissions, and activity feed."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from aspirant.ui.theme import PALETTE
from aspirant.ui.widgets.glass import GlassCard, SectionHeader, StatTile, StatusPill


class HomeDashboardView(QWidget):
    """Primary command center displaying system health, mic status, providers, and activity."""

    def __init__(
        self,
        on_toggle_restricted: Callable[[bool], None],
        on_navigate: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_toggle_restricted = on_toggle_restricted
        self._on_navigate = on_navigate
        self._restricted_active = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        self.root_layout = QVBoxLayout(container)
        self.root_layout.setContentsMargins(24, 20, 24, 24)
        self.root_layout.setSpacing(16)

        self.header = SectionHeader(
            "ASPIRANT AI Command Center",
            "Personal digital operating companion • Local-first & permission-gated",
            badge_text="ONLINE",
            tone="ok",
        )
        self.root_layout.addWidget(self.header)

        # Hero Status Card
        hero = GlassCard()
        hero_row = QHBoxLayout()
        left_col = QVBoxLayout()
        left_col.setSpacing(4)
        self.assistant_status_lbl = QLabel("Assistant Status: Ready & Listening on Command")
        self.assistant_status_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #FFFFFF;")
        self.active_task_lbl = QLabel("Active Task: Idle — Ready")
        self.active_task_lbl.setProperty("role", "mono")
        self.mic_status_lbl = QLabel("Microphone Hardware: Checking WinMM endpoints...")
        self.mic_status_lbl.setProperty("role", "subtitle")
        left_col.addWidget(self.assistant_status_lbl)
        left_col.addWidget(self.active_task_lbl)
        left_col.addWidget(self.mic_status_lbl)

        right_col = QVBoxLayout()
        right_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.restricted_btn = QPushButton("Restricted Mode: OFF")
        self.restricted_btn.setProperty("variant", "ghost")
        self.restricted_btn.clicked.connect(self._handle_restricted_click)
        self.open_security_btn = QPushButton("Open Security Center")
        self.open_security_btn.setProperty("variant", "primary")
        self.open_security_btn.clicked.connect(lambda: self._on_navigate("security"))
        right_col.addWidget(self.restricted_btn)
        right_col.addWidget(self.open_security_btn)

        hero_row.addLayout(left_col, 1)
        hero_row.addLayout(right_col)
        hero.body_layout.addLayout(hero_row)
        self.root_layout.addWidget(hero)

        # Telemetry Row
        telemetry_grid = QGridLayout()
        telemetry_grid.setSpacing(12)
        self.cpu_tile = StatTile("CPU Utilization")
        self.sys_ram_tile = StatTile("System Memory (8 GB Host)")
        self.app_ram_tile = StatTile("Aspirant Footprint")
        self.disk_tile = StatTile("Storage & Network")
        telemetry_grid.addWidget(self.cpu_tile, 0, 0)
        telemetry_grid.addWidget(self.sys_ram_tile, 0, 1)
        telemetry_grid.addWidget(self.app_ram_tile, 0, 2)
        telemetry_grid.addWidget(self.disk_tile, 0, 3)
        self.root_layout.addLayout(telemetry_grid)

        # Middle Split: Providers + Permissions
        mid_row = QHBoxLayout()
        mid_row.setSpacing(14)

        self.providers_card = GlassCard()
        prov_hdr = QHBoxLayout()
        prov_title = QLabel("Connected AI Providers")
        prov_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        prov_btn = QPushButton("View All Models")
        prov_btn.setProperty("variant", "ghost")
        prov_btn.clicked.connect(lambda: self._on_navigate("models"))
        prov_hdr.addWidget(prov_title)
        prov_hdr.addStretch(1)
        prov_hdr.addWidget(prov_btn)
        self.providers_card.body_layout.addLayout(prov_hdr)
        self.providers_list_layout = QVBoxLayout()
        self.providers_list_layout.setSpacing(8)
        self.providers_card.body_layout.addLayout(self.providers_list_layout)
        self.providers_card.body_layout.addStretch(1)

        self.perms_card = GlassCard()
        perm_hdr = QHBoxLayout()
        perm_title = QLabel("Permission Matrix")
        perm_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.perm_summary_pill = StatusPill("SAFE DEFAULTS", "ok")
        perm_hdr.addWidget(perm_title)
        perm_hdr.addStretch(1)
        perm_hdr.addWidget(self.perm_summary_pill)
        self.perms_card.body_layout.addLayout(perm_hdr)
        self.perms_grid = QGridLayout()
        self.perms_grid.setSpacing(8)
        self._perm_pills: dict[str, StatusPill] = {}
        for idx, perm in enumerate(("READ", "WRITE", "EXECUTE", "BROWSER", "ADMIN", "NETWORK")):
            row_card = GlassCard(subtle=True)
            r_layout = QHBoxLayout()
            lbl = QLabel(perm)
            lbl.setStyleSheet("font-weight: 600;")
            pill = StatusPill("OFF", "muted")
            self._perm_pills[perm] = pill
            r_layout.addWidget(lbl)
            r_layout.addStretch(1)
            r_layout.addWidget(pill)
            row_card.body_layout.addLayout(r_layout)
            self.perms_grid.addWidget(row_card, idx // 2, idx % 2)
        self.perms_card.body_layout.addLayout(self.perms_grid)

        mid_row.addWidget(self.providers_card, 1)
        mid_row.addWidget(self.perms_card, 1)
        self.root_layout.addLayout(mid_row)

        # Recent Activity Table
        activity_card = GlassCard()
        act_hdr = QHBoxLayout()
        act_title = QLabel("Recent Security & System Activity")
        act_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        act_note = QLabel("Live from audit.db")
        act_note.setStyleSheet(f"color: {PALETTE['text_muted']}; font-size: 11px;")
        act_hdr.addWidget(act_title)
        act_hdr.addStretch(1)
        act_hdr.addWidget(act_note)
        activity_card.body_layout.addLayout(act_hdr)

        self.activity_table = QTableWidget(0, 5)
        self.activity_table.setHorizontalHeaderLabels(
            ["Time (UTC)", "Category", "Action", "Permission", "Outcome"]
        )
        self.activity_table.verticalHeader().setVisible(False)
        self.activity_table.setAlternatingRowColors(True)
        self.activity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.activity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.activity_table.setMinimumHeight(200)
        hdr = self.activity_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        activity_card.body_layout.addWidget(self.activity_table)
        self.root_layout.addWidget(activity_card)

    def _handle_restricted_click(self) -> None:
        self._on_toggle_restricted(not self._restricted_active)

    def update_state(self, overview: dict[str, Any], audit_items: list[dict[str, Any]]) -> None:
        """Refresh all dashboard panels from live backend JSON."""
        telemetry = overview.get("telemetry", {})
        security = overview.get("security", {})
        providers = overview.get("providers", [])
        ram_budget = int(overview.get("ram_budget_mb", 320))

        stopped = bool(security.get("emergency_stop_active", False))
        restricted = bool(security.get("restricted_mode", False))
        self._restricted_active = restricted

        if stopped:
            self.header.badge.set_tone("danger", "EMERGENCY STOP")
            self.assistant_status_lbl.setText("Assistant Status: HALTED — Emergency Stop Engaged")
        elif restricted:
            self.header.badge.set_tone("warn", "RESTRICTED")
            self.assistant_status_lbl.setText("Assistant Status: Active (Restricted Read-Only Mode)")
        else:
            self.header.badge.set_tone("ok", "ONLINE")
            self.assistant_status_lbl.setText("Assistant Status: Online & Permission-Guarded")

        self.active_task_lbl.setText(f"Active Task: {overview.get('active_task', 'Idle')}")
        audio = telemetry.get("audio", {})
        mic_ok = bool(audio.get("mic_available", False))
        spk_ok = bool(audio.get("speaker_available", False))
        self.mic_status_lbl.setText(
            f"Audio Hardware: Mic {'Detected' if mic_ok else 'Missing'} ({audio.get('mic_count', 0)}) • "
            f"Speaker {'Detected' if spk_ok else 'Missing'} ({audio.get('speaker_count', 0)}) • Voice Pipeline: Phase 3"
        )

        self.restricted_btn.setText(f"Restricted Mode: {'ON' if restricted else 'OFF'}")

        cpu_pct = float(telemetry.get("cpu_percent", 0.0))
        self.cpu_tile.update_metric(
            f"{cpu_pct:.1f}%",
            cpu_pct,
            f"{telemetry.get('cpu_cores', 0)} cores / {telemetry.get('cpu_threads', 0)} threads",
            tone="warn" if cpu_pct > 80 else "ok",
            badge_text="HIGH" if cpu_pct > 80 else "NORMAL",
        )

        ram_pct = float(telemetry.get("ram_percent", 0.0))
        ram_avail = int(telemetry.get("ram_available_mb", 0))
        ram_total = int(telemetry.get("ram_total_mb", 0))
        self.sys_ram_tile.update_metric(
            f"{ram_pct:.1f}%",
            ram_pct,
            f"{ram_avail} MB free of {ram_total} MB",
            tone="warn" if ram_pct > 88 else "info",
            badge_text="TIGHT" if ram_pct > 88 else "OK",
        )

        app_ram = float(telemetry.get("app_ram_mb", 0.0))
        budget_pct = (app_ram / max(1, ram_budget)) * 100.0
        self.app_ram_tile.update_metric(
            f"{app_ram:.0f} MB",
            budget_pct,
            f"Target idle budget <= {ram_budget} MB",
            tone="ok" if app_ram <= ram_budget else "warn",
            badge_text="LEAN" if app_ram <= ram_budget else "HEAVY",
        )

        disk_pct = float(telemetry.get("disk_percent", 0.0))
        self.disk_tile.update_metric(
            f"{telemetry.get('disk_free_gb', 0)} GB free",
            disk_pct,
            f"Net ↓ {telemetry.get('net_rx_kbps', 0)} KB/s • ↑ {telemetry.get('net_tx_kbps', 0)} KB/s",
            tone="info",
            badge_text="C:\\ NTFS",
        )

        # Update Providers summary
        while self.providers_list_layout.count():
            item = self.providers_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for prov in providers:
            row_card = GlassCard(subtle=True)
            row = QHBoxLayout()
            name_col = QVBoxLayout()
            name_col.setSpacing(1)
            n_lbl = QLabel(str(prov.get("name", "")))
            n_lbl.setStyleSheet("font-weight: 600;")
            r_lbl = QLabel(str(prov.get("role", "")))
            r_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; font-size: 11px;")
            name_col.addWidget(n_lbl)
            name_col.addWidget(r_lbl)
            configured = bool(prov.get("configured", False))
            pill = StatusPill(
                "READY" if configured else "KEY NEEDED",
                "ok" if configured else "warn",
            )
            row.addLayout(name_col, 1)
            row.addWidget(pill)
            row_card.body_layout.addLayout(row)
            self.providers_list_layout.addWidget(row_card)

        # Update Permission pills
        perms = security.get("permissions", {})
        for name, pill in self._perm_pills.items():
            enabled = bool(perms.get(name, False))
            if stopped:
                pill.set_tone("danger", "STOPPED")
            elif restricted and name in {"WRITE", "EXECUTE", "BROWSER", "ADMIN"}:
                pill.set_tone("warn", "LOCKED")
            elif enabled:
                pill.set_tone("ok" if name != "ADMIN" else "warn", "ON")
            else:
                pill.set_tone("muted", "OFF")

        if stopped:
            self.perm_summary_pill.set_tone("danger", "EMERGENCY LOCK")
        elif restricted:
            self.perm_summary_pill.set_tone("warn", "RESTRICTED MODE")
        else:
            self.perm_summary_pill.set_tone("ok", "POLICY ACTIVE")

        # Update Audit table (latest 10)
        recent = audit_items[:10]
        self.activity_table.setRowCount(len(recent))
        for row_idx, item in enumerate(recent):
            ts = str(item.get("timestamp", ""))[:19].replace("T", " ")
            self.activity_table.setItem(row_idx, 0, QTableWidgetItem(ts))
            self.activity_table.setItem(row_idx, 1, QTableWidgetItem(str(item.get("category", ""))))
            self.activity_table.setItem(row_idx, 2, QTableWidgetItem(str(item.get("action", ""))))
            self.activity_table.setItem(row_idx, 3, QTableWidgetItem(str(item.get("permission", ""))))
            self.activity_table.setItem(
                row_idx,
                4,
                QTableWidgetItem(f"{item.get('decision', '')} ({item.get('status', '')})"),
            )
