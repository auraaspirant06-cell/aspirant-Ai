"""Image Studio view: AI generation/editing, thumbnails, diagrams, bg removal, and passport sheets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from aspirant.ui.client import AspirantApiClient
from aspirant.ui.theme import PALETTE
from aspirant.ui.widgets.glass import GlassCard, SectionHeader, StatusPill


class ImageStudioView(QWidget):
    """Creative image generation, editing, diagram, and Indian passport-sheet studio."""

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
            "AI Image Studio",
            "Nano Banana 2.1 • OpenAI • Local Posters/Thumbnails • Diagrams • 300 DPI Passport Sheets",
            badge_text="STUDIO",
            tone="accent",
        )
        layout.addWidget(self.header)

        gen_card = GlassCard()
        row1 = QHBoxLayout()
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Describe an image, thumbnail title, or comma-separated diagram steps...")
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("Gemini Nano Banana 2.1", "gemini")
        self.provider_combo.addItem("OpenAI Images", "openai")
        self.provider_combo.addItem("Local Poster/Thumbnail Canvas (Free)", "local-canvas")
        self.ratio_combo = QComboBox()
        for r in ("16:9", "1:1", "9:16", "4:5"):
            self.ratio_combo.addItem(r, r)
        gen_btn = QPushButton("Generate Image")
        gen_btn.setProperty("variant", "primary")
        gen_btn.clicked.connect(self._generate)
        diag_btn = QPushButton("Make Diagram")
        diag_btn.setProperty("variant", "ghost")
        diag_btn.clicked.connect(self._make_diagram)
        row1.addWidget(self.prompt_input, 2)
        row1.addWidget(self.provider_combo)
        row1.addWidget(self.ratio_combo)
        row1.addWidget(gen_btn)
        row1.addWidget(diag_btn)
        gen_card.body_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Existing image path (for Remove BG or 35x45mm Passport Photo Sheet)...")
        nobg_btn = QPushButton("Remove Background")
        nobg_btn.setProperty("variant", "ghost")
        nobg_btn.clicked.connect(self._remove_bg)
        pass_btn = QPushButton("300 DPI Passport Sheet")
        pass_btn.setProperty("variant", "ghost")
        pass_btn.clicked.connect(self._passport_sheet)
        self.status_pill = StatusPill("READY", "info")
        row2.addWidget(self.file_input, 1)
        row2.addWidget(nobg_btn)
        row2.addWidget(pass_btn)
        row2.addWidget(self.status_pill)
        gen_card.body_layout.addLayout(row2)
        layout.addWidget(gen_card)

        preview_card = GlassCard()
        self.info_lbl = QLabel("Generated artwork or passport sheet will preview here.")
        self.info_lbl.setWordWrap(True)
        self.info_lbl.setStyleSheet(f"color: {PALETTE['text_secondary']};")
        self.preview_lbl = QLabel("No image rendered yet.")
        self.preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_lbl.setMinimumHeight(340)
        preview_card.body_layout.addWidget(self.info_lbl)
        preview_card.body_layout.addWidget(self.preview_lbl, 1)
        layout.addWidget(preview_card)

    def _show_image(self, res: dict[str, Any]) -> None:
        path = str(res.get("path", ""))
        self.status_pill.set_tone("ok", "SAVED")
        self.info_lbl.setText(f"Output: {path}")
        if path and Path(path).exists():
            pix = QPixmap(path)
            self.preview_lbl.setPixmap(
                pix.scaled(680, 340, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )

    def _generate(self) -> None:
        prompt = self.prompt_input.text().strip()
        if not prompt:
            return
        try:
            res = self.api_client._request(
                "POST",
                "/api/v1/media/image/generate",
                json={
                    "prompt": prompt,
                    "provider": str(self.provider_combo.currentData()),
                    "aspect_ratio": str(self.ratio_combo.currentData()),
                },
                timeout=60.0,
            )
            self._show_image(res)
        except Exception as exc:
            self.status_pill.set_tone("danger", "ERROR")
            self.info_lbl.setText(str(exc))

    def _make_diagram(self) -> None:
        raw = self.prompt_input.text().strip() or "Prompt, Script, Storyboard, Voiceover, Final Video"
        steps = [s.strip() for s in raw.split(",") if s.strip()]
        try:
            res = self.api_client._request(
                "POST",
                "/api/v1/media/image/diagram",
                json={"title": "Workflow Diagram", "steps": steps},
            )
            self._show_image(res)
        except Exception as exc:
            self.status_pill.set_tone("danger", "ERROR")
            self.info_lbl.setText(str(exc))

    def _remove_bg(self) -> None:
        p = self.file_input.text().strip()
        if not p:
            return
        try:
            res = self.api_client._request("POST", "/api/v1/media/image/remove-bg", json={"image_path": p})
            self._show_image(res)
        except Exception as exc:
            self.status_pill.set_tone("danger", "ERROR")
            self.info_lbl.setText(str(exc))

    def _passport_sheet(self) -> None:
        p = self.file_input.text().strip()
        if not p:
            return
        try:
            res = self.api_client._request(
                "POST", "/api/v1/media/image/passport-sheet", json={"portrait_path": p, "copies": 8}
            )
            self._show_image(res)
        except Exception as exc:
            self.status_pill.set_tone("danger", "ERROR")
            self.info_lbl.setText(str(exc))
