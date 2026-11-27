"""AI Video Studio view: Prompt -> Script -> Storyboard -> Scenes -> Voiceover -> Subtitles -> MP4."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QCheckBox,
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

from aspirant.ui.client import AspirantApiClient
from aspirant.ui.theme import PALETTE
from aspirant.ui.widgets.glass import GlassCard, SectionHeader, StatusPill


class VideoStudioView(QWidget):
    """Text-to-video, script-to-video, Reels/Shorts, and Gemini Omni 1.2 Flash studio."""

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
            "AI Video Generation Studio",
            "Reels/Shorts (9:16) • Explainers (16:9) • Female Voiceover • Hindi/English Subtitles • MP4",
            badge_text="HONEST PIPELINE",
            tone="accent",
        )
        layout.addWidget(self.header)

        cfg_card = GlassCard()
        row1 = QHBoxLayout()
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("Gemini Omni 1.2 Flash (Generative AI Video)", "omni")
        self.engine_combo.addItem("Storyboard + Female Voiceover + SRT -> MP4 (Local/Free)", "storyboard")
        self.ratio_combo = QComboBox()
        for r in ("9:16", "16:9", "1:1"):
            self.ratio_combo.addItem(r, r)
        self.style_combo = QComboBox()
        for st in ("reels", "explainer", "educational", "cinematic"):
            self.style_combo.addItem(st.title(), st)
        self.vo_chk = QCheckBox("Include Female Voiceover")
        self.vo_chk.setChecked(True)
        row1.addWidget(QLabel("Engine:"))
        row1.addWidget(self.engine_combo, 1)
        row1.addWidget(QLabel("Aspect:"))
        row1.addWidget(self.ratio_combo)
        row1.addWidget(QLabel("Style:"))
        row1.addWidget(self.style_combo)
        row1.addWidget(self.vo_chk)
        cfg_card.body_layout.addLayout(row1)

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Video prompt or topic (English, Hindi, or Hinglish)...")
        cfg_card.body_layout.addWidget(self.prompt_input)

        self.script_box = QTextEdit()
        self.script_box.setFixedHeight(110)
        self.script_box.setPlaceholderText(
            "Optional custom script (one scene per line). Leave blank to auto-generate script & storyboard."
        )
        self.script_box.setStyleSheet(
            "QTextEdit { background: rgba(10, 14, 28, 0.88); color: #F8FAFC; border-radius: 8px; padding: 8px; }"
        )
        cfg_card.body_layout.addWidget(self.script_box)

        row2 = QHBoxLayout()
        self.first_frame_input = QLineEdit()
        self.first_frame_input.setPlaceholderText("Optional first-frame image path (for Image-to-Video)...")
        render_btn = QPushButton("Create Video (MP4)")
        render_btn.setProperty("variant", "primary")
        render_btn.clicked.connect(self._create_video)
        self.status_pill = StatusPill("READY", "info")
        row2.addWidget(self.first_frame_input, 1)
        row2.addWidget(render_btn)
        row2.addWidget(self.status_pill)
        cfg_card.body_layout.addLayout(row2)
        layout.addWidget(cfg_card)

        out_card = GlassCard()
        honest_lbl = QLabel(
            "Honesty Rule: Cloud generative video reports FAILED if the provider is unconfigured or returns no video."
        )
        honest_lbl.setStyleSheet(f"color: {PALETTE['neon_cyan']}; font-size: 11px;")
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setMinimumHeight(200)
        self.output_box.setStyleSheet(
            "QTextEdit { background: rgba(8, 12, 24, 0.92); color: #A5F3FC; font-family: Consolas, monospace; border-radius: 8px; padding: 8px; }"
        )
        out_card.body_layout.addWidget(honest_lbl)
        out_card.body_layout.addWidget(self.output_box)
        layout.addWidget(out_card)

    def _create_video(self) -> None:
        prompt = self.prompt_input.text().strip()
        if not prompt:
            return
        engine = str(self.engine_combo.currentData())
        ratio = str(self.ratio_combo.currentData())
        try:
            if engine == "omni":
                res = self.api_client._request(
                    "POST",
                    "/api/v1/media/video/generative",
                    json={
                        "prompt": prompt,
                        "aspect_ratio": ratio,
                        "first_frame_path": self.first_frame_input.text().strip() or None,
                    },
                    timeout=180.0,
                )
            else:
                res = self.api_client._request(
                    "POST",
                    "/api/v1/media/video/storyboard",
                    json={
                        "prompt": prompt,
                        "video_style": str(self.style_combo.currentData()),
                        "aspect_ratio": ratio,
                        "script_override": self.script_box.toPlainText().strip() or None,
                        "include_voiceover": self.vo_chk.isChecked(),
                    },
                    timeout=120.0,
                )
            ok = res.get("status") == "completed"
            self.status_pill.set_tone("ok" if ok else "danger", "COMPLETED" if ok else "FAILED")
            self.output_box.setPlainText(json.dumps(res, indent=2, ensure_ascii=False))
        except Exception as exc:
            self.status_pill.set_tone("danger", "FAILED")
            self.output_box.setPlainText(str(exc))
