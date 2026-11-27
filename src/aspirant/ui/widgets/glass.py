"""Reusable glassmorphic UI building blocks."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from aspirant.ui.theme import PALETTE


class GlassCard(QFrame):
    """Translucent bordered card used across all dashboard and studio views."""

    def __init__(self, parent: QWidget | None = None, subtle: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("SubtleCard" if subtle else "GlassCard")
        self.body_layout = QVBoxLayout(self)
        self.body_layout.setContentsMargins(16, 14, 16, 14)
        self.body_layout.setSpacing(10)


class StatusPill(QLabel):
    """Compact colored pill indicator."""

    def __init__(self, text: str = "", tone: str = "info", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_tone(tone)

    def set_tone(self, tone: str, text: str | None = None) -> None:
        if text is not None:
            self.setText(text)
        colors = {
            "ok": ("rgba(16, 185, 129, 0.18)", "#34D399", "rgba(16, 185, 129, 0.45)"),
            "warn": ("rgba(245, 158, 11, 0.18)", "#FBBF24", "rgba(245, 158, 11, 0.45)"),
            "danger": ("rgba(239, 68, 68, 0.22)", "#F87171", "rgba(239, 68, 68, 0.55)"),
            "accent": ("rgba(124, 58, 237, 0.24)", "#C4B5FD", "rgba(139, 92, 246, 0.50)"),
            "info": ("rgba(34, 211, 238, 0.16)", "#67E8F9", "rgba(34, 211, 238, 0.40)"),
            "muted": ("rgba(100, 116, 139, 0.18)", "#CBD5E1", "rgba(148, 163, 184, 0.30)"),
        }
        bg, fg, border = colors.get(tone, colors["info"])
        self.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border: 1px solid {border}; "
            "border-radius: 10px; padding: 3px 10px; font-size: 11px; font-weight: 700;"
        )


class StatTile(GlassCard):
    """Live telemetry KPI card with title, headline value, progress bar, and detail."""

    def __init__(self, title: str, initial_value: str = "--", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        header = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "subtitle")
        self.badge = StatusPill("LIVE", "info")
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.badge)
        self.body_layout.addLayout(header)

        self.value_label = QLabel(initial_value)
        self.value_label.setProperty("role", "metric-value")
        self.body_layout.addWidget(self.value_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.body_layout.addWidget(self.progress)

        self.detail_label = QLabel("Sampling...")
        self.detail_label.setStyleSheet(f"color: {PALETTE['text_muted']}; font-size: 11px;")
        self.body_layout.addWidget(self.detail_label)

    def update_metric(
        self,
        value_text: str,
        percent: float,
        detail_text: str,
        tone: str = "info",
        badge_text: str = "OK",
    ) -> None:
        self.value_label.setText(value_text)
        self.progress.setValue(max(0, min(100, int(round(percent)))))
        self.detail_label.setText(detail_text)
        self.badge.set_tone(tone, badge_text)


class SectionHeader(QWidget):
    """Consistent view header with title, subtitle, and right-aligned pill."""

    def __init__(
        self, title: str, subtitle: str, badge_text: str = "READY", tone: str = "ok", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setProperty("role", "title")
        sub_lbl = QLabel(subtitle)
        sub_lbl.setWordWrap(True)
        sub_lbl.setProperty("role", "subtitle")
        text_col.addWidget(title_lbl)
        text_col.addWidget(sub_lbl)
        layout.addLayout(text_col, 1)
        self.badge = StatusPill(badge_text, tone)
        layout.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
