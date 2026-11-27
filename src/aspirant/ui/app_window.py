"""Main PySide6 desktop window featuring 13 sections, top bar, tray icon, and Emergency Stop."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from aspirant import APP_NAME, __version__
from aspirant.ui.client import AspirantApiClient
from aspirant.ui.theme import PALETTE, build_stylesheet
from aspirant.ui.views.chat_view import ChatView
from aspirant.ui.views.coding_view import CodingStudioView
from aspirant.ui.views.files_view import FileManagerView
from aspirant.ui.views.gov_view import GovServicesView
from aspirant.ui.views.home_view import HomeDashboardView
from aspirant.ui.views.image_view import ImageStudioView
from aspirant.ui.views.memory_view import MemoryManagerView
from aspirant.ui.views.models_settings_views import ModelsView, SettingsView
from aspirant.ui.views.pc_control_view import PCControlView
from aspirant.ui.views.security_view import SecurityCenterView
from aspirant.ui.views.video_view import VideoStudioView
from aspirant.ui.views.voice_view import VoiceAssistantView
from aspirant.ui.widgets.glass import StatusPill


NAV_SECTIONS: list[tuple[str, str, str]] = [
    ("CORE", "home", "Home Dashboard"),
    ("CORE", "voice", "Live Voice Assistant"),
    ("CORE", "chat", "Chat"),
    ("STUDIOS", "pc_control", "PC Control"),
    ("STUDIOS", "coding", "Coding Studio"),
    ("STUDIOS", "gov", "Government Services"),
    ("STUDIOS", "video", "AI Video Studio"),
    ("STUDIOS", "image", "Image Studio"),
    ("STUDIOS", "files", "File Manager"),
    ("SYSTEM", "memory", "Memory"),
    ("SYSTEM", "models", "Connected AI Models"),
    ("SYSTEM", "security", "Security Center"),
    ("SYSTEM", "settings", "Settings"),
]


class _PollWorker(QObject):
    """Background worker fetching overview + audit logs without stalling Qt UI."""

    data_ready = Signal(dict, list)
    health_ready = Signal(list, list)
    failed = Signal(str)

    def __init__(self, client: AspirantApiClient) -> None:
        super().__init__()
        self.client = client
        self.category = "all"

    @Slot()
    def fetch(self) -> None:
        try:
            overview = self.client.get_overview()
            logs = self.client.get_audit_logs(limit=40, category=self.category).get("items", [])
            self.data_ready.emit(overview, logs)
        except Exception as exc:
            self.failed.emit(str(exc))

    @Slot()
    def fetch_health(self) -> None:
        try:
            data = self.client.check_provider_health()
            self.health_ready.emit(data.get("health", []), data.get("usage", []))
        except Exception as exc:
            self.failed.emit(str(exc))


def _create_app_icon() -> QIcon:
    repo_root = Path(__file__).resolve().parents[3]
    for candidate in (
        repo_root / "docs" / "brand" / "assets" / "app-icon-512.png",
        repo_root / "desktop" / "assets" / "app-icon.png",
    ):
        if candidate.exists():
            icon = QIcon(str(candidate))
            if not icon.isNull():
                return icon
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(PALETTE["purple"]))
    painter.setPen(QColor(PALETTE["neon_cyan"]))
    painter.drawEllipse(6, 6, 52, 52)
    painter.setPen(QColor("#FFFFFF"))
    font = painter.font()
    font.setPointSize(24)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "A")
    painter.end()
    return QIcon(pixmap)


class AspirantMainWindow(QMainWindow):
    """Unified 13-section dark glassmorphic desktop window for ASPIRANT AI."""

    poll_requested = Signal()
    health_requested = Signal()

    def __init__(self, api_client: AspirantApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self._audit_category = "all"

        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.setWindowIcon(_create_app_icon())
        self.resize(1320, 840)
        self.setMinimumSize(980, 660)
        self.setStyleSheet(build_stylesheet())

        root = QWidget()
        root.setObjectName("RootWindow")
        self.setCentralWidget(root)
        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(14, 16, 14, 14)
        side_layout.setSpacing(4)

        brand = QLabel("ASPIRANT AI")
        brand.setStyleSheet(
            f"font-size: 18px; font-weight: 800; letter-spacing: 1px; color: {PALETTE['neon_cyan']};"
        )
        sub_brand = QLabel("Personal Operating Companion")
        sub_brand.setStyleSheet(f"color: {PALETTE['text_muted']}; font-size: 11px; margin-bottom: 8px;")
        side_layout.addWidget(brand)
        side_layout.addWidget(sub_brand)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons: dict[str, QPushButton] = {}
        self._view_indices: dict[str, int] = {}

        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.viewport().setStyleSheet("background: transparent;")
        nav_container = QWidget()
        nav_container.setStyleSheet("background: transparent;")
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 2, 0)
        nav_layout.setSpacing(3)

        last_group = ""
        for group, key, label in NAV_SECTIONS:
            if group != last_group:
                g_lbl = QLabel(group)
                g_lbl.setProperty("role", "section-label")
                nav_layout.addWidget(g_lbl)
                last_group = group
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("nav", "true")
            btn.setMinimumHeight(34)
            btn.clicked.connect(lambda _checked, k=key: self.navigate_to(k))
            self._nav_group.addButton(btn)
            self._nav_buttons[key] = btn
            nav_layout.addWidget(btn)

        nav_layout.addStretch(1)
        nav_scroll.setWidget(nav_container)
        side_layout.addWidget(nav_scroll, 1)

        self.sidebar_ram_lbl = QLabel("Footprint: -- MB")
        self.sidebar_ram_lbl.setProperty("role", "mono")
        side_layout.addWidget(self.sidebar_ram_lbl)
        main_layout.addWidget(sidebar)

        # Right column: TopBar + Stacked Views
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(56)
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(20, 8, 20, 8)
        top_layout.setSpacing(10)

        self.top_status_pill = StatusPill("CONNECTING...", "info")
        self.top_mic_pill = StatusPill("MIC: CHECKING", "muted")
        self.top_mode_pill = StatusPill("NORMAL POLICY", "ok")

        self.emergency_btn = QPushButton("EMERGENCY STOP")
        self.emergency_btn.setProperty("variant", "danger")
        self.emergency_btn.clicked.connect(self._trigger_emergency_stop)

        top_layout.addWidget(self.top_status_pill)
        top_layout.addWidget(self.top_mic_pill)
        top_layout.addWidget(self.top_mode_pill)
        top_layout.addStretch(1)
        top_layout.addWidget(self.emergency_btn)
        right_layout.addWidget(topbar)

        self.stack = QStackedWidget()
        self._stack_opacity = QGraphicsOpacityEffect(self.stack)
        self._stack_opacity.setOpacity(1.0)
        self.stack.setGraphicsEffect(self._stack_opacity)
        self._fade_anim = QPropertyAnimation(self._stack_opacity, b"opacity", self)
        self._fade_anim.setDuration(150)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        right_layout.addWidget(self.stack, 1)
        main_layout.addWidget(right_col, 1)

        self._build_views()
        self.navigate_to("home")

        # Global window hotkey for Emergency Stop
        self._stop_shortcut = QShortcut(QKeySequence("Ctrl+Alt+Shift+E"), self)
        self._stop_shortcut.activated.connect(self._trigger_emergency_stop)

        # Background polling thread + timer (non-blocking UI)
        self._poll_thread = QThread(self)
        self._poll_worker = _PollWorker(self.api_client)
        self._poll_worker.moveToThread(self._poll_thread)
        self.poll_requested.connect(self._poll_worker.fetch)
        self.health_requested.connect(self._poll_worker.fetch_health)
        self._poll_worker.data_ready.connect(self._on_backend_data)
        self._poll_worker.health_ready.connect(self.models_view.update_health_and_usage)
        self._poll_worker.failed.connect(self._on_backend_error)
        self._poll_thread.start()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self._request_poll)
        self._poll_timer.start()
        QTimer.singleShot(50, self._request_poll)

        self._init_tray()

    def _build_views(self) -> None:
        self.home_view = HomeDashboardView(
            on_toggle_restricted=self._set_restricted_mode,
            on_navigate=self.navigate_to,
        )
        self.voice_view = VoiceAssistantView(api_client=self.api_client)
        self.chat_view = ChatView(api_client=self.api_client)
        self.pc_control_view = PCControlView(api_client=self.api_client)
        self.coding_view = CodingStudioView(api_client=self.api_client)
        self.gov_view = GovServicesView(api_client=self.api_client)
        self.video_view = VideoStudioView(api_client=self.api_client)
        self.image_view = ImageStudioView(api_client=self.api_client)
        self.files_view = FileManagerView(api_client=self.api_client)
        self.memory_view = MemoryManagerView(api_client=self.api_client)
        self.models_view = ModelsView(
            on_health_check=lambda: self.health_requested.emit(),
            on_save_key=self._save_provider_key,
        )
        self.security_view = SecurityCenterView(
            on_permission_change=self._set_permission,
            on_restricted_change=self._set_restricted_mode,
            on_emergency_stop=self._trigger_emergency_stop,
            on_resume=self._resume_system,
            on_refresh_logs=self._on_audit_filter_changed,
        )
        self.settings_view = SettingsView()

        views: dict[str, QWidget] = {
            "home": self.home_view,
            "voice": self.voice_view,
            "chat": self.chat_view,
            "pc_control": self.pc_control_view,
            "coding": self.coding_view,
            "gov": self.gov_view,
            "video": self.video_view,
            "image": self.image_view,
            "files": self.files_view,
            "memory": self.memory_view,
            "models": self.models_view,
            "security": self.security_view,
            "settings": self.settings_view,
        }

        for key, widget in views.items():
            idx = self.stack.addWidget(widget)
            self._view_indices[key] = idx

    def navigate_to(self, key: str) -> None:
        if key not in self._view_indices:
            return
        self._nav_buttons[key].setChecked(True)
        self.stack.setCurrentIndex(self._view_indices[key])
        if key == "chat":
            self.chat_view.refresh_conversations()
        elif key == "files":
            self.files_view.load_directory()
        elif key == "memory":
            self.memory_view.refresh_preferences()
        self._fade_anim.stop()
        self._fade_anim.setStartValue(0.65)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def _init_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(_create_app_icon(), self)
        menu = QMenu()
        show_action = QAction("Show ASPIRANT AI", self)
        show_action.triggered.connect(self.showNormal)
        stop_action = QAction("EMERGENCY STOP", self)
        stop_action.triggered.connect(self._trigger_emergency_stop)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        menu.addAction(show_action)
        menu.addAction(stop_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.setToolTip(f"{APP_NAME} v{__version__}")
        self._tray.show()

    def _request_poll(self) -> None:
        self._poll_worker.category = self._audit_category
        self.poll_requested.emit()

    @Slot(dict, list)
    def _on_backend_data(self, overview: dict, audit_items: list) -> None:
        tel = overview.get("telemetry", {})
        sec = overview.get("security", {})
        audio = tel.get("audio", {})

        self.top_status_pill.set_tone("ok", "CORE API: CONNECTED")
        self.top_mic_pill.set_tone(
            "info" if audio.get("mic_available") else "warn",
            f"MIC: {'READY' if audio.get('mic_available') else 'NOT FOUND'}",
        )
        if sec.get("emergency_stop_active"):
            self.top_mode_pill.set_tone("danger", "EMERGENCY STOP")
        elif sec.get("restricted_mode"):
            self.top_mode_pill.set_tone("warn", "RESTRICTED MODE")
        else:
            self.top_mode_pill.set_tone("ok", "POLICY ACTIVE")

        self.sidebar_ram_lbl.setText(f"RAM: {tel.get('app_ram_mb', 0):.0f} MB")

        self.home_view.update_state(overview, audit_items)
        self.voice_view.update_status(overview.get("voice", {}))
        self.security_view.update_state(sec, audit_items)
        self.models_view.update_providers(overview.get("providers", []))
        self.settings_view.update_overview(overview)

    @Slot(str)
    def _on_backend_error(self, message: str) -> None:
        self.top_status_pill.set_tone("danger", "API DISCONNECTED")
        self.top_status_pill.setToolTip(message)

    def _run_mutation(self, fn: Callable[[], dict]) -> None:
        try:
            fn()
            self._request_poll()
        except Exception as exc:
            self.top_status_pill.set_tone("danger", "ACTION FAILED")
            self.top_status_pill.setToolTip(str(exc))

    def _save_provider_key(self, key_name: str, value: str) -> None:
        self._run_mutation(lambda: self.api_client.configure_provider_key(key_name, value))

    def _set_permission(self, perm: str, granted: bool) -> None:
        self._run_mutation(lambda: self.api_client.set_permission(perm, granted))

    def _set_restricted_mode(self, enabled: bool) -> None:
        self._run_mutation(lambda: self.api_client.set_restricted_mode(enabled))

    def _trigger_emergency_stop(self) -> None:
        self._run_mutation(lambda: self.api_client.trigger_emergency_stop("UI Emergency STOP"))

    def _resume_system(self) -> None:
        self._run_mutation(self.api_client.resume_system)

    def _on_audit_filter_changed(self, category: str) -> None:
        self._audit_category = category
        self._request_poll()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._poll_timer.stop()
        self._poll_thread.quit()
        self._poll_thread.wait(1500)
        self.voice_view.shutdown()
        self.chat_view.shutdown()
        if hasattr(self, "_tray"):
            self._tray.hide()
        super().closeEvent(event)
