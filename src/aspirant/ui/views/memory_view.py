"""Smart Memory view: search conversation history, edit/delete preferences, and encrypted backup."""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
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

from aspirant.ui.client import AspirantApiClient
from aspirant.ui.theme import PALETTE
from aspirant.ui.widgets.glass import GlassCard, SectionHeader, StatusPill


class MemoryManagerView(QWidget):
    """Local-first memory inspector, preference editor, FTS5 search, and encrypted backup manager."""

    def __init__(self, api_client: AspirantApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(12)

        self.header = SectionHeader(
            "Smart Local Memory",
            "SQLite + FTS5 searchable history • Preference editor • Zero-secret policy • Encrypted backup",
            badge_text="LOCAL-FIRST",
            tone="ok",
        )
        layout.addWidget(self.header)

        # FTS5 Conversation Search
        search_card = GlassCard()
        s_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search past conversations (FTS5)...")
        s_btn = QPushButton("Search History")
        s_btn.setProperty("variant", "primary")
        s_btn.clicked.connect(self._search_history)
        self.status_pill = StatusPill("READY", "info")
        s_row.addWidget(self.search_input, 1)
        s_row.addWidget(s_btn)
        s_row.addWidget(self.status_pill)
        search_card.body_layout.addLayout(s_row)

        self.search_table = QTableWidget(0, 4)
        self.search_table.setHorizontalHeaderLabels(["Time", "Role", "Language", "Content"])
        self.search_table.verticalHeader().setVisible(False)
        self.search_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.search_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.search_table.setMinimumHeight(140)
        search_card.body_layout.addWidget(self.search_table)
        layout.addWidget(search_card)

        # Preferences Editor
        pref_card = GlassCard()
        p_hdr = QHBoxLayout()
        p_lbl = QLabel("Remembered User Preferences (Passwords/Keys/OTPs Blocked)")
        p_lbl.setStyleSheet("font-size: 14px; font-weight: 700;")
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setProperty("variant", "ghost")
        refresh_btn.clicked.connect(self.refresh_preferences)
        del_btn = QPushButton("Delete Selected")
        del_btn.setProperty("variant", "danger")
        del_btn.clicked.connect(self._delete_selected_pref)
        p_hdr.addWidget(p_lbl)
        p_hdr.addStretch(1)
        p_hdr.addWidget(refresh_btn)
        p_hdr.addWidget(del_btn)
        pref_card.body_layout.addLayout(p_hdr)

        add_row = QHBoxLayout()
        self.pref_key = QLineEdit()
        self.pref_key.setPlaceholderText("Key (e.g. coding_style)")
        self.pref_val = QLineEdit()
        self.pref_val.setPlaceholderText("Value (e.g. concise Python + type hints)")
        self.pref_cat = QComboBox()
        self.pref_cat.addItems(["communication", "coding", "projects", "workflows", "general"])
        save_btn = QPushButton("Save Preference")
        save_btn.setProperty("variant", "primary")
        save_btn.clicked.connect(self._save_preference)
        add_row.addWidget(self.pref_key, 1)
        add_row.addWidget(self.pref_val, 2)
        add_row.addWidget(self.pref_cat)
        add_row.addWidget(save_btn)
        pref_card.body_layout.addLayout(add_row)

        self.pref_table = QTableWidget(0, 4)
        self.pref_table.setHorizontalHeaderLabels(["Key", "Value", "Category", "Updated"])
        self.pref_table.verticalHeader().setVisible(False)
        self.pref_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.pref_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.pref_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.pref_table.setMinimumHeight(150)
        pref_card.body_layout.addWidget(self.pref_table)
        layout.addWidget(pref_card)

        # Encrypted Backup Export
        bk_card = GlassCard(subtle=True)
        bk_row = QHBoxLayout()
        self.backup_pass = QLineEdit()
        self.backup_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.backup_pass.setPlaceholderText("Enter backup passphrase (min 6 chars)...")
        bk_btn = QPushButton("Export Encrypted Backup (.aspbk)")
        bk_btn.setProperty("variant", "primary")
        bk_btn.clicked.connect(self._export_backup)
        self.backup_out = QLabel("Creates PBKDF2+AES encrypted archive of memory.db, audit.db & vault.enc.")
        self.backup_out.setWordWrap(True)
        self.backup_out.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 11px;")
        bk_row.addWidget(self.backup_pass, 1)
        bk_row.addWidget(bk_btn)
        bk_card.body_layout.addLayout(bk_row)
        bk_card.body_layout.addWidget(self.backup_out)
        layout.addWidget(bk_card)

    def refresh_preferences(self) -> None:
        try:
            items = self.api_client._request("GET", "/api/v1/memory/preferences").get("items", [])
            self.pref_table.setRowCount(len(items))
            for r, it in enumerate(items):
                self.pref_table.setItem(r, 0, QTableWidgetItem(str(it.get("key", ""))))
                self.pref_table.setItem(r, 1, QTableWidgetItem(json.dumps(it.get("value", ""), ensure_ascii=False)))
                self.pref_table.setItem(r, 2, QTableWidgetItem(str(it.get("category", ""))))
                self.pref_table.setItem(r, 3, QTableWidgetItem(str(it.get("updated_at", ""))[:19]))
        except Exception:
            pass

    def _search_history(self) -> None:
        q = self.search_input.text().strip()
        if not q:
            return
        try:
            items = self.api_client._request("GET", "/api/v1/memory/search", params={"q": q}).get("items", [])
            self.search_table.setRowCount(len(items))
            for r, it in enumerate(items):
                self.search_table.setItem(r, 0, QTableWidgetItem(str(it.get("created_at", ""))[:19]))
                self.search_table.setItem(r, 1, QTableWidgetItem(str(it.get("role", ""))))
                self.search_table.setItem(r, 2, QTableWidgetItem(str(it.get("language", ""))))
                self.search_table.setItem(r, 3, QTableWidgetItem(str(it.get("content", ""))))
            self.status_pill.set_tone("ok", f"{len(items)} HITS")
        except Exception as exc:
            self.status_pill.set_tone("danger", "ERROR")
            self.backup_out.setText(str(exc))

    def _save_preference(self) -> None:
        k = self.pref_key.text().strip()
        v = self.pref_val.text().strip()
        if not k:
            return
        try:
            self.api_client._request(
                "POST",
                "/api/v1/memory/preferences",
                json={"key": k, "value": v, "category": self.pref_cat.currentText()},
            )
            self.pref_key.clear()
            self.pref_val.clear()
            self.status_pill.set_tone("ok", "SAVED")
            self.refresh_preferences()
        except Exception as exc:
            self.status_pill.set_tone("danger", "BLOCKED")
            self.backup_out.setText(str(exc))

    def _delete_selected_pref(self) -> None:
        row = self.pref_table.currentRow()
        if row < 0:
            return
        key = self.pref_table.item(row, 0).text()
        try:
            self.api_client._request("DELETE", f"/api/v1/memory/preferences/{key}")
            self.refresh_preferences()
        except Exception as exc:
            self.backup_out.setText(str(exc))

    def _export_backup(self) -> None:
        pw = self.backup_pass.text().strip()
        if not pw:
            return
        try:
            res = self.api_client._request("POST", "/api/v1/memory/backup", json={"passphrase": pw})
            self.backup_pass.clear()
            self.backup_out.setText(f"Encrypted backup created: {res['path']} ({res['bytes']} bytes)")
        except Exception as exc:
            self.backup_out.setText(f"Backup failed: {exc}")
