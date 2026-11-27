"""Sandboxed File Manager view with browse, search, preview, folder organization, and reversible trash."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from aspirant.ui.client import AspirantApiClient
from aspirant.ui.theme import PALETTE
from aspirant.ui.widgets.glass import GlassCard, SectionHeader, StatusPill


class FileManagerView(QWidget):
    """Interactive file explorer & organizer with protected-path and trash-safe guards."""

    def __init__(self, api_client: AspirantApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self._current_dir = str((Path.home() / "Documents").resolve())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(12)

        self.header = SectionHeader(
            "File Manager",
            "Sandboxed file browse, search, preview, smart folder organization & reversible trash",
            badge_text="SAFE PATHS",
            tone="ok",
        )
        layout.addWidget(self.header)

        # Address + Search Bar
        bar = GlassCard(subtle=True)
        row1 = QHBoxLayout()
        self.path_input = QLineEdit(self._current_dir)
        go_btn = QPushButton("Open Folder")
        go_btn.setProperty("variant", "primary")
        go_btn.clicked.connect(self.load_directory)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search filename...")
        search_btn = QPushButton("Search")
        search_btn.setProperty("variant", "ghost")
        search_btn.clicked.connect(self._search)
        row1.addWidget(QLabel("Path:"))
        row1.addWidget(self.path_input, 2)
        row1.addWidget(go_btn)
        row1.addWidget(self.search_input, 1)
        row1.addWidget(search_btn)
        bar.body_layout.addLayout(row1)

        row2 = QHBoxLayout()
        preview_org_btn = QPushButton("Preview Smart Organize")
        preview_org_btn.setProperty("variant", "ghost")
        preview_org_btn.clicked.connect(lambda: self._organize(dry_run=True))
        apply_org_btn = QPushButton("Apply Smart Organize")
        apply_org_btn.setProperty("variant", "ghost")
        apply_org_btn.clicked.connect(lambda: self._organize(dry_run=False))
        trash_btn = QPushButton("Move Selected to Trash")
        trash_btn.setProperty("variant", "danger")
        trash_btn.clicked.connect(self._trash_selected)
        self.status_pill = StatusPill("READY", "info")
        row2.addWidget(preview_org_btn)
        row2.addWidget(apply_org_btn)
        row2.addWidget(trash_btn)
        row2.addStretch(1)
        row2.addWidget(self.status_pill)
        bar.body_layout.addLayout(row2)
        layout.addWidget(bar)

        # Split Table + Preview
        split = QHBoxLayout()
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Size (B)", "Path"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self._on_row_double_click)

        preview_card = GlassCard()
        p_lbl = QLabel("File Preview / Organize Plan")
        p_lbl.setStyleSheet("font-size: 14px; font-weight: 700;")
        self.preview_box = QTextEdit()
        self.preview_box.setReadOnly(True)
        self.preview_box.setStyleSheet(
            "QTextEdit { background: rgba(10, 14, 28, 0.85); color: #E2E8F0; border-radius: 8px; padding: 8px; font-family: Consolas, monospace; }"
        )
        preview_card.body_layout.addWidget(p_lbl)
        preview_card.body_layout.addWidget(self.preview_box, 1)

        split.addWidget(self.table, 3)
        split.addWidget(preview_card, 2)
        layout.addLayout(split, 1)

    def load_directory(self) -> None:
        path = self.path_input.text().strip()
        if not path:
            return
        try:
            res = self.api_client.files_list(path)
            self._current_dir = res["path"]
            self.path_input.setText(self._current_dir)
            self._populate(res.get("entries", []))
            self.status_pill.set_tone("ok", f"{len(res.get('entries', []))} ITEMS")
        except Exception as exc:
            self.status_pill.set_tone("danger", "BLOCKED")
            self.preview_box.setPlainText(str(exc))

    def _populate(self, entries: list[dict[str, Any]]) -> None:
        self.table.setRowCount(len(entries))
        for r, item in enumerate(entries):
            self.table.setItem(r, 0, QTableWidgetItem(str(item.get("name", ""))))
            self.table.setItem(r, 1, QTableWidgetItem("DIR" if item.get("is_dir") else "FILE"))
            self.table.setItem(r, 2, QTableWidgetItem(str(item.get("size_bytes", 0))))
            self.table.setItem(r, 3, QTableWidgetItem(str(item.get("path", ""))))

    def _on_row_double_click(self, row: int, _col: int) -> None:
        kind = self.table.item(row, 1).text()
        path = self.table.item(row, 3).text()
        if kind == "DIR":
            self.path_input.setText(path)
            self.load_directory()
            return
        try:
            data = self.api_client.files_read(path)
            self.preview_box.setPlainText(data.get("content", ""))
        except Exception as exc:
            self.preview_box.setPlainText(f"Cannot preview file: {exc}")

    def _search(self) -> None:
        pat = self.search_input.text().strip()
        if not pat:
            return
        try:
            hits = self.api_client.files_search(self.path_input.text().strip(), pat)
            self._populate(hits)
            self.status_pill.set_tone("info", f"{len(hits)} MATCHES")
        except Exception as exc:
            self.preview_box.setPlainText(str(exc))

    def _organize(self, dry_run: bool) -> None:
        try:
            res = self.api_client.files_organize(self.path_input.text().strip(), dry_run=dry_run)
            moves = res.get("planned_moves", [])
            lines = [f"{'PREVIEW' if dry_run else 'APPLIED'}: {len(moves)} file(s)"]
            for m in moves[:40]:
                lines.append(f"  [{m['category']}] {Path(m['src']).name} -> {m['dst']}")
            self.preview_box.setPlainText("\n".join(lines))
            if not dry_run:
                self.load_directory()
        except Exception as exc:
            self.status_pill.set_tone("danger", "WRITE NEEDED")
            self.preview_box.setPlainText(str(exc))

    def _trash_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        path = self.table.item(row, 3).text()
        try:
            res = self.api_client.files_trash(path)
            self.preview_box.setPlainText(f"Moved to reversible trash:\n{res.get('trash_path')}")
            self.load_directory()
        except Exception as exc:
            self.status_pill.set_tone("danger", "BLOCKED")
            self.preview_box.setPlainText(str(exc))
