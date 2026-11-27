"""Dark glassmorphic design tokens and QSS stylesheet for ASPIRANT AI."""

from __future__ import annotations


PALETTE = {
    "bg_canvas": "#070A14",
    "bg_sidebar": "#0B1020",
    "bg_surface": "rgba(18, 24, 46, 0.84)",
    "bg_surface_alt": "rgba(25, 34, 62, 0.88)",
    "border_glass": "rgba(139, 92, 246, 0.24)",
    "border_subtle": "rgba(148, 163, 184, 0.16)",
    "purple": "#7C3AED",
    "purple_bright": "#8B5CF6",
    "blue": "#3B82F6",
    "neon_cyan": "#22D3EE",
    "emerald": "#10B981",
    "amber": "#F59E0B",
    "crimson": "#EF4444",
    "text_primary": "#F8FAFC",
    "text_secondary": "#94A3B8",
    "text_muted": "#64748B",
}


def build_stylesheet() -> str:
    """Return the application-wide futuristic dark glassmorphic QSS."""
    return f"""
    QMainWindow, QWidget#RootWindow {{
        background-color: {PALETTE['bg_canvas']};
        color: {PALETTE['text_primary']};
        font-family: "Segoe UI", "Arial", sans-serif;
        font-size: 13px;
    }}

    QFrame#Sidebar {{
        background-color: {PALETTE['bg_sidebar']};
        border-right: 1px solid {PALETTE['border_subtle']};
    }}

    QFrame#TopBar {{
        background-color: rgba(11, 16, 32, 0.92);
        border-bottom: 1px solid {PALETTE['border_subtle']};
    }}

    QFrame#GlassCard {{
        background-color: {PALETTE['bg_surface']};
        border: 1px solid {PALETTE['border_glass']};
        border-radius: 14px;
    }}

    QFrame#SubtleCard {{
        background-color: {PALETTE['bg_surface_alt']};
        border: 1px solid {PALETTE['border_subtle']};
        border-radius: 12px;
    }}

    QLabel {{
        color: {PALETTE['text_primary']};
        background: transparent;
    }}

    QLabel[role="title"] {{
        font-size: 21px;
        font-weight: 700;
        color: #FFFFFF;
    }}

    QLabel[role="subtitle"] {{
        font-size: 13px;
        color: {PALETTE['text_secondary']};
    }}

    QLabel[role="section-label"] {{
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
        color: {PALETTE['text_muted']};
        padding-top: 8px;
        padding-bottom: 2px;
    }}

    QLabel[role="metric-value"] {{
        font-size: 22px;
        font-weight: 700;
        color: #FFFFFF;
    }}

    QLabel[role="mono"] {{
        font-family: "Cascadia Code", "Consolas", monospace;
        font-size: 12px;
        color: {PALETTE['neon_cyan']};
    }}

    QPushButton[nav="true"] {{
        text-align: left;
        padding: 9px 14px;
        border-radius: 10px;
        border: 1px solid transparent;
        background-color: transparent;
        color: {PALETTE['text_secondary']};
        font-weight: 500;
    }}

    QPushButton[nav="true"]:hover {{
        background-color: rgba(124, 58, 237, 0.14);
        color: #FFFFFF;
        border: 1px solid rgba(139, 92, 246, 0.25);
    }}

    QPushButton[nav="true"]:checked {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(124, 58, 237, 0.34),
            stop:1 rgba(59, 130, 246, 0.22)
        );
        color: #FFFFFF;
        font-weight: 600;
        border: 1px solid rgba(34, 211, 238, 0.42);
    }}

    QPushButton[variant="primary"] {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {PALETTE['purple']},
            stop:1 {PALETTE['blue']}
        );
        color: #FFFFFF;
        border: none;
        border-radius: 9px;
        padding: 8px 16px;
        font-weight: 600;
    }}

    QPushButton[variant="primary"]:hover {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {PALETTE['purple_bright']},
            stop:1 #60A5FA
        );
    }}

    QPushButton[variant="danger"] {{
        background-color: rgba(239, 68, 68, 0.90);
        color: #FFFFFF;
        border: 1px solid #FCA5A5;
        border-radius: 9px;
        padding: 7px 14px;
        font-weight: 700;
    }}

    QPushButton[variant="danger"]:hover {{
        background-color: #DC2626;
    }}

    QPushButton[variant="ghost"] {{
        background-color: rgba(30, 41, 59, 0.65);
        color: {PALETTE['text_primary']};
        border: 1px solid {PALETTE['border_subtle']};
        border-radius: 8px;
        padding: 7px 13px;
        font-weight: 500;
    }}

    QPushButton[variant="ghost"]:hover {{
        border: 1px solid {PALETTE['neon_cyan']};
        background-color: rgba(34, 211, 238, 0.12);
    }}

    QProgressBar {{
        background-color: rgba(15, 23, 42, 0.85);
        border: 1px solid {PALETTE['border_subtle']};
        border-radius: 5px;
        height: 8px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        border-radius: 4px;
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {PALETTE['purple']},
            stop:1 {PALETTE['neon_cyan']}
        );
    }}

    QCheckBox {{
        color: {PALETTE['text_primary']};
        spacing: 8px;
    }}

    QComboBox, QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
        background-color: rgba(15, 23, 42, 0.92);
        color: {PALETTE['text_primary']};
        border: 1px solid {PALETTE['border_subtle']};
        border-radius: 8px;
        padding: 6px 10px;
        min-height: 20px;
    }}

    QComboBox:focus, QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {PALETTE['neon_cyan']};
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 24px;
        border-left: 1px solid {PALETTE['border_subtle']};
    }}

    QComboBox QAbstractItemView {{
        background-color: #0F172A;
        color: #F8FAFC;
        border: 1px solid {PALETTE['border_glass']};
        selection-background-color: {PALETTE['purple']};
        selection-color: #FFFFFF;
        outline: 0px;
        padding: 4px;
    }}

    QMenu {{
        background-color: #0B1020;
        color: #F8FAFC;
        border: 1px solid {PALETTE['border_glass']};
        border-radius: 8px;
        padding: 4px;
    }}

    QMenu::item {{
        padding: 6px 16px;
        border-radius: 5px;
    }}

    QMenu::item:selected {{
        background-color: {PALETTE['purple']};
        color: #FFFFFF;
    }}

    QTableWidget {{
        background-color: rgba(12, 17, 32, 0.72);
        alternate-background-color: rgba(22, 30, 56, 0.55);
        border: 1px solid {PALETTE['border_subtle']};
        border-radius: 10px;
        gridline-color: rgba(148, 163, 184, 0.10);
        color: {PALETTE['text_primary']};
    }}

    QHeaderView::section {{
        background-color: rgba(17, 24, 46, 0.95);
        color: {PALETTE['text_secondary']};
        padding: 7px 10px;
        border: none;
        border-bottom: 1px solid {PALETTE['border_subtle']};
        font-weight: 600;
    }}

    QScrollArea,
    QScrollArea > QWidget,
    QScrollArea > QWidget > QWidget {{
        border: none;
        background-color: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px;
    }}

    QScrollBar::handle:vertical {{
        background: rgba(148, 163, 184, 0.25);
        border-radius: 4px;
        min-height: 24px;
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """
