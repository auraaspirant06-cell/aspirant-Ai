"""Security Center view: RBAC permissions, Restricted Mode, Kill Switch, and Audit Log."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aspirant.ui.theme import PALETTE
from aspirant.ui.widgets.glass import GlassCard, SectionHeader, StatusPill


PERMISSION_DESCRIPTIONS = {
    "READ": "Read files, inspect project structures, and query local status.",
    "WRITE": "Create, edit, rename, or move local files (trash-safe delete rules apply).",
    "EXECUTE": "Run inspected terminal commands, tests, and permitted desktop actions.",
    "BROWSER": "Control the isolated Playwright Edge profile (blocks personal cookies/OTP).",
    "ADMIN": "High-privilege system operations (still requires per-action explicit approval).",
    "NETWORK": "Call configured external AI APIs and verified .gov.in/.nic.in portals.",
}


class SecurityCenterView(QWidget):
    """Interactive security governance, kill switch, and live audit log explorer."""

    def __init__(
        self,
        on_permission_change: Callable[[str, bool], None],
        on_restricted_change: Callable[[bool], None],
        on_emergency_stop: Callable[[], None],
        on_resume: Callable[[], None],
        on_refresh_logs: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_permission_change = on_permission_change
        self._on_restricted_change = on_restricted_change
        self._on_emergency_stop = on_emergency_stop
        self._on_resume = on_resume
        self._on_refresh_logs = on_refresh_logs
        self._syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(14)

        self.header = SectionHeader(
            "Security Center",
            "Granular RBAC permissions, Restricted Mode, Emergency Stop, and tamper-audited activity logs",
            badge_text="ENFORCED",
            tone="ok",
        )
        layout.addWidget(self.header)

        # Emergency + Restricted Mode Banner
        control_card = GlassCard()
        ctrl_row = QHBoxLayout()
        info_col = QVBoxLayout()
        self.lock_status_lbl = QLabel("Execution Safety State: Normal Policy Enforcement")
        self.lock_status_lbl.setStyleSheet("font-size: 14px; font-weight: 700;")
        self.lock_hint_lbl = QLabel(
            "Emergency STOP immediately halts automation & code tasks. Restricted Mode locks all modifications."
        )
        self.lock_hint_lbl.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 12px;")
        info_col.addWidget(self.lock_status_lbl)
        info_col.addWidget(self.lock_hint_lbl)

        self.restricted_chk = QCheckBox("Restricted Mode (Read-Only Safe Lock)")
        self.restricted_chk.toggled.connect(self._handle_restricted_toggle)

        self.stop_btn = QPushButton("EMERGENCY STOP (Ctrl+Alt+Shift+E)")
        self.stop_btn.setProperty("variant", "danger")
        self.stop_btn.clicked.connect(self._on_emergency_stop)

        self.resume_btn = QPushButton("Resume Operations")
        self.resume_btn.setProperty("variant", "primary")
        self.resume_btn.clicked.connect(self._on_resume)

        ctrl_row.addLayout(info_col, 1)
        ctrl_row.addWidget(self.restricted_chk)
        ctrl_row.addWidget(self.stop_btn)
        ctrl_row.addWidget(self.resume_btn)
        control_card.body_layout.addLayout(ctrl_row)
        layout.addWidget(control_card)

        # Permission Matrix
        perm_card = GlassCard()
        perm_title = QLabel("Capability Permission Matrix")
        perm_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        perm_card.body_layout.addWidget(perm_title)

        grid = QGridLayout()
        grid.setSpacing(10)
        self._checkboxes: dict[str, QCheckBox] = {}
        self._status_pills: dict[str, StatusPill] = {}

        for idx, (perm, desc) in enumerate(PERMISSION_DESCRIPTIONS.items()):
            tile = GlassCard(subtle=True)
            top = QHBoxLayout()
            chk = QCheckBox(perm)
            chk.setStyleSheet("font-weight: 700;")
            chk.toggled.connect(lambda checked, p=perm: self._handle_perm_toggle(p, checked))
            pill = StatusPill("OFF", "muted")
            self._checkboxes[perm] = chk
            self._status_pills[perm] = pill
            top.addWidget(chk)
            top.addStretch(1)
            top.addWidget(pill)
            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; font-size: 11px;")
            tile.body_layout.addLayout(top)
            tile.body_layout.addWidget(desc_lbl)
            grid.addWidget(tile, idx // 2, idx % 2)
        perm_card.body_layout.addLayout(grid)
        layout.addWidget(perm_card)

        # Audit Log Table
        audit_card = GlassCard()
        toolbar = QHBoxLayout()
        audit_title = QLabel("Audit Log Explorer")
        audit_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.category_filter = QComboBox()
        self.category_filter.addItems(["all", "system", "security", "permissions", "emergency"])
        self.category_filter.currentTextChanged.connect(self._on_refresh_logs)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setProperty("variant", "ghost")
        refresh_btn.clicked.connect(lambda: self._on_refresh_logs(self.category_filter.currentText()))
        toolbar.addWidget(audit_title)
        toolbar.addStretch(1)
        toolbar.addWidget(QLabel("Category:"))
        toolbar.addWidget(self.category_filter)
        toolbar.addWidget(refresh_btn)
        audit_card.body_layout.addLayout(toolbar)

        self.audit_table = QTableWidget(0, 6)
        self.audit_table.setHorizontalHeaderLabels(
            ["ID", "Timestamp (UTC)", "Category", "Action", "Permission", "Decision / Status"]
        )
        self.audit_table.verticalHeader().setVisible(False)
        self.audit_table.setAlternatingRowColors(True)
        self.audit_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hdr = self.audit_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        audit_card.body_layout.addWidget(self.audit_table, 1)
        layout.addWidget(audit_card, 1)

    def _handle_perm_toggle(self, perm: str, checked: bool) -> None:
        if not self._syncing:
            self._on_permission_change(perm, checked)

    def _handle_restricted_toggle(self, checked: bool) -> None:
        if not self._syncing:
            self._on_restricted_change(checked)

    def update_state(self, security: dict[str, Any], audit_items: list[dict[str, Any]]) -> None:
        """Synchronize UI toggles and audit table with persisted backend state."""
        self._syncing = True
        try:
            stopped = bool(security.get("emergency_stop_active", False))
            restricted = bool(security.get("restricted_mode", False))
            perms = security.get("permissions", {})

            self.restricted_chk.setChecked(restricted)
            self.resume_btn.setEnabled(stopped)

            if stopped:
                self.header.badge.set_tone("danger", "EMERGENCY LOCK")
                self.lock_status_lbl.setText("Execution Safety State: EMERGENCY STOP ENGAGED")
            elif restricted:
                self.header.badge.set_tone("warn", "RESTRICTED")
                self.lock_status_lbl.setText("Execution Safety State: Restricted Read-Only Mode")
            else:
                self.header.badge.set_tone("ok", "ENFORCED")
                self.lock_status_lbl.setText("Execution Safety State: Normal Policy Enforcement")

            for perm, chk in self._checkboxes.items():
                enabled = bool(perms.get(perm, False))
                chk.setChecked(enabled)
                pill = self._status_pills[perm]
                if stopped:
                    pill.set_tone("danger", "HALTED")
                elif restricted and perm in {"WRITE", "EXECUTE", "BROWSER", "ADMIN"}:
                    pill.set_tone("warn", "BLOCKED BY RESTRICTED")
                elif enabled:
                    pill.set_tone("ok" if perm != "ADMIN" else "warn", "ENABLED")
                else:
                    pill.set_tone("muted", "DISABLED")
        finally:
            self._syncing = False

        self.audit_table.setRowCount(len(audit_items))
        for idx, item in enumerate(audit_items):
            ts = str(item.get("timestamp", ""))[:19].replace("T", " ")
            self.audit_table.setItem(idx, 0, QTableWidgetItem(str(item.get("id", ""))))
            self.audit_table.setItem(idx, 1, QTableWidgetItem(ts))
            self.audit_table.setItem(idx, 2, QTableWidgetItem(str(item.get("category", ""))))
            self.audit_table.setItem(idx, 3, QTableWidgetItem(str(item.get("action", ""))))
            self.audit_table.setItem(idx, 4, QTableWidgetItem(str(item.get("permission", ""))))
            self.audit_table.setItem(
                idx, 5, QTableWidgetItem(f"{item.get('decision', '')} / {item.get('status', '')}")
            )
