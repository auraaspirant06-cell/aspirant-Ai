"""Multilingual Adaptive Chat Studio view with live streaming and 7 personalities."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from aspirant.personality.language_detect import SUPPORTED_LANGUAGES
from aspirant.personality.personas import PERSONAS
from aspirant.ui.client import AspirantApiClient
from aspirant.ui.theme import PALETTE
from aspirant.ui.widgets.glass import GlassCard, SectionHeader, StatusPill


class _ChatStreamWorker(QObject):
    """Streams chat SSE events on a background QThread."""

    meta_received = Signal(dict)
    delta_received = Signal(str)
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, client: AspirantApiClient) -> None:
        super().__init__()
        self.client = client
        self.payload: dict[str, Any] = {}

    @Slot()
    def run(self) -> None:
        try:
            for event in self.client.stream_chat(**self.payload):
                etype = event.get("event")
                if etype == "meta":
                    self.meta_received.emit(event)
                elif etype == "delta":
                    self.delta_received.emit(str(event.get("text", "")))
                elif etype == "done":
                    self.completed.emit(event)
                elif etype == "error":
                    self.failed.emit(str(event.get("detail", "Chat failed")))
                    return
        except Exception as exc:
            self.failed.emit(str(exc))


class ChatView(QWidget):
    """Interactive multilingual chat workspace with conversation sidebar and persona modes."""

    send_requested = Signal()

    def __init__(self, api_client: AspirantApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self.current_conversation_id: str | None = None
        self._active_reply_label: QLabel | None = None
        self._streaming_text = ""

        root = QHBoxLayout(self)
        root.setContentsMargins(18, 16, 20, 18)
        root.setSpacing(14)

        # Left Conversations Panel
        conv_panel = GlassCard()
        conv_panel.setFixedWidth(250)
        conv_top = QHBoxLayout()
        conv_lbl = QLabel("Conversations")
        conv_lbl.setStyleSheet("font-size: 14px; font-weight: 700;")
        new_btn = QPushButton("+ New")
        new_btn.setProperty("variant", "primary")
        new_btn.clicked.connect(self.start_new_chat)
        conv_top.addWidget(conv_lbl)
        conv_top.addStretch(1)
        conv_top.addWidget(new_btn)
        conv_panel.body_layout.addLayout(conv_top)

        self.conv_list = QListWidget()
        self.conv_list.setStyleSheet(
            "QListWidget { background: rgba(12, 17, 32, 0.7); border: 1px solid rgba(148,163,184,0.16); border-radius: 10px; padding: 4px; }"
            "QListWidget::item { padding: 8px; border-radius: 6px; color: #E2E8F0; }"
            "QListWidget::item:selected { background: rgba(124, 58, 237, 0.35); color: #FFFFFF; }"
        )
        self.conv_list.itemClicked.connect(self._on_conversation_selected)
        conv_panel.body_layout.addWidget(self.conv_list, 1)

        del_btn = QPushButton("Delete Selected")
        del_btn.setProperty("variant", "ghost")
        del_btn.clicked.connect(self._delete_selected_conversation)
        conv_panel.body_layout.addWidget(del_btn)
        root.addWidget(conv_panel)

        # Main Chat Workspace
        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        self.header = SectionHeader(
            "Chat Companion",
            "Hindi, Hinglish, English & 18+ Indian languages • Adaptive tone & zero fake translation",
            badge_text="READY",
            tone="ok",
        )
        right_col.addWidget(self.header)

        # Controls Bar
        controls = GlassCard(subtle=True)
        ctrl_row = QHBoxLayout()
        self.persona_combo = QComboBox()
        for p in PERSONAS.values():
            self.persona_combo.addItem(p.name, p.id)

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("Auto (Gemini Primary)", "auto")
        self.provider_combo.addItem("Google Gemini", "gemini")
        self.provider_combo.addItem("OpenAI-Compatible", "openai")
        self.provider_combo.addItem("Groq", "groq")
        self.provider_combo.addItem("Ollama (Local)", "ollama")

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Auto-Detect Language", "auto")
        for code, (label, _script) in SUPPORTED_LANGUAGES.items():
            self.lang_combo.addItem(f"{label} ({code})", code)

        self.detected_pill = StatusPill("LANG: AUTO", "info")

        ctrl_row.addWidget(QLabel("Personality:"))
        ctrl_row.addWidget(self.persona_combo)
        ctrl_row.addWidget(QLabel("Provider:"))
        ctrl_row.addWidget(self.provider_combo)
        ctrl_row.addWidget(QLabel("Language:"))
        ctrl_row.addWidget(self.lang_combo)
        ctrl_row.addStretch(1)
        ctrl_row.addWidget(self.detected_pill)
        controls.body_layout.addLayout(ctrl_row)
        right_col.addWidget(controls)

        # Transcript Area
        self.transcript_scroll = QScrollArea()
        self.transcript_scroll.setWidgetResizable(True)
        self.transcript_container = QWidget()
        self.transcript_layout = QVBoxLayout(self.transcript_container)
        self.transcript_layout.setContentsMargins(6, 6, 6, 6)
        self.transcript_layout.setSpacing(10)
        self.transcript_layout.addStretch(1)
        self.transcript_scroll.setWidget(self.transcript_container)
        right_col.addWidget(self.transcript_scroll, 1)

        # Input Composer
        composer = GlassCard()
        comp_row = QHBoxLayout()
        self.input_box = QTextEdit()
        self.input_box.setFixedHeight(74)
        self.input_box.setPlaceholderText(
            "Ask in English, Hindi (नमस्ते), Hinglish (bhai code samjhao), Bengali, Tamil, Marathi..."
        )
        self.input_box.setStyleSheet(
            "QTextEdit { background: rgba(15, 23, 42, 0.85); color: #F8FAFC; border: 1px solid rgba(148,163,184,0.22); border-radius: 10px; padding: 8px; }"
        )
        self.send_btn = QPushButton("Send")
        self.send_btn.setProperty("variant", "primary")
        self.send_btn.setMinimumHeight(46)
        self.send_btn.clicked.connect(self.send_current_message)
        comp_row.addWidget(self.input_box, 1)
        comp_row.addWidget(self.send_btn)
        composer.body_layout.addLayout(comp_row)
        right_col.addWidget(composer)
        root.addLayout(right_col, 1)

        # Background stream worker
        self._thread = QThread(self)
        self._worker = _ChatStreamWorker(self.api_client)
        self._worker.moveToThread(self._thread)
        self.send_requested.connect(self._worker.run)
        self._worker.meta_received.connect(self._on_meta)
        self._worker.delta_received.connect(self._on_delta)
        self._worker.completed.connect(self._on_completed)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def refresh_conversations(self) -> None:
        try:
            items = self.api_client.list_conversations()
        except Exception:
            return
        self.conv_list.clear()
        for item in items:
            list_item = QListWidgetItem(f"{item['title']}\n[{item['language']} • {item['persona']}]")
            list_item.setData(Qt.ItemDataRole.UserRole, item["id"])
            self.conv_list.addItem(list_item)

    def start_new_chat(self) -> None:
        self.current_conversation_id = None
        self._clear_transcript()
        self.detected_pill.set_tone("info", "NEW CHAT")

    def _clear_transcript(self) -> None:
        while self.transcript_layout.count() > 1:
            item = self.transcript_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._active_reply_label = None

    def _append_bubble(self, role: str, text: str, badge: str = "") -> QLabel:
        card = GlassCard(subtle=(role == "user"))
        hdr = QHBoxLayout()
        who = QLabel("You" if role == "user" else "ASPIRANT AI")
        who.setStyleSheet(
            f"font-weight: 700; color: {PALETTE['neon_cyan'] if role == 'assistant' else '#C4B5FD'};"
        )
        hdr.addWidget(who)
        hdr.addStretch(1)
        if badge:
            hdr.addWidget(StatusPill(badge, "accent" if role == "assistant" else "muted"))
        card.body_layout.addLayout(hdr)

        body_lbl = QLabel(text)
        body_lbl.setWordWrap(True)
        body_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body_lbl.setStyleSheet("font-size: 13px; line-height: 1.45;")
        card.body_layout.addWidget(body_lbl)

        # Insert before trailing stretch
        self.transcript_layout.insertWidget(self.transcript_layout.count() - 1, card)
        sb = self.transcript_scroll.verticalScrollBar()
        sb.setValue(sb.maximum())
        return body_lbl

    def _on_conversation_selected(self, item: QListWidgetItem) -> None:
        cid = item.data(Qt.ItemDataRole.UserRole)
        if not cid:
            return
        try:
            data = self.api_client.get_conversation(cid)
        except Exception:
            return
        self.current_conversation_id = cid
        self._clear_transcript()
        for msg in data.get("messages", []):
            meta = msg.get("metadata", {})
            badge = msg.get("language", "")
            if meta.get("model"):
                badge = f"{badge} • {meta['model']}"
            self._append_bubble(msg["role"], msg["content"], badge=badge)

    def _delete_selected_conversation(self) -> None:
        item = self.conv_list.currentItem()
        if not item:
            return
        cid = item.data(Qt.ItemDataRole.UserRole)
        try:
            self.api_client.delete_conversation(cid)
        except Exception:
            return
        if self.current_conversation_id == cid:
            self.start_new_chat()
        self.refresh_conversations()

    def send_current_message(self) -> None:
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        self.input_box.clear()
        self.send_btn.setEnabled(False)
        self.header.badge.set_tone("accent", "THINKING...")
        self._append_bubble("user", text, badge=str(self.persona_combo.currentData()))
        self._streaming_text = ""
        self._active_reply_label = self._append_bubble("assistant", "Thinking...", badge="STREAM")

        self._worker.payload = {
            "message": text,
            "conversation_id": self.current_conversation_id,
            "persona_id": str(self.persona_combo.currentData()),
            "provider_id": str(self.provider_combo.currentData()),
            "language_override": str(self.lang_combo.currentData()),
        }
        self.send_requested.emit()

    @Slot(dict)
    def _on_meta(self, meta: dict[str, Any]) -> None:
        self.current_conversation_id = meta.get("conversation_id")
        lang = meta.get("detected_language", {})
        self.detected_pill.set_tone("info", f"LANG: {lang.get('label', 'Auto').upper()}")
        switched = meta.get("switched_persona")
        if switched:
            idx = self.persona_combo.findData(switched)
            if idx >= 0:
                self.persona_combo.setCurrentIndex(idx)

    @Slot(str)
    def _on_delta(self, delta: str) -> None:
        self._streaming_text += delta
        if self._active_reply_label is not None:
            self._active_reply_label.setText(self._streaming_text)

    @Slot(dict)
    def _on_completed(self, event: dict[str, Any]) -> None:
        self.send_btn.setEnabled(True)
        self.header.badge.set_tone("ok", "READY")
        msg = event.get("message", {})
        if self._active_reply_label is not None and msg.get("content"):
            self._active_reply_label.setText(msg["content"])
        self.refresh_conversations()

    @Slot(str)
    def _on_failed(self, detail: str) -> None:
        self.send_btn.setEnabled(True)
        self.header.badge.set_tone("warn", "CHECK PROVIDER")
        if self._active_reply_label is not None:
            self._active_reply_label.setText(f"Could not complete reply: {detail}")

    def shutdown(self) -> None:
        self._thread.quit()
        self._thread.wait(1200)
