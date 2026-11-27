"""Phase 9 full end-to-end desktop + loopback Uvicorn + WebSocket verification."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fastapi.testclient import TestClient
import httpx
import psutil
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import uvicorn

from aspirant.core.config import AppSettings
from aspirant.server.app import build_container, create_app
from aspirant.ui.app_window import NAV_SECTIONS, AspirantMainWindow
from aspirant.ui.client import AspirantApiClient
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


def test_websocket_auth_and_connected_frame(tmp_path: Path) -> None:
    settings = AppSettings(ASPIRANT_DATA_DIR=tmp_path / "data")
    container = build_container(settings)
    app = create_app(settings=settings, container=container)
    client = TestClient(app)

    with client:
        # Unauthenticated WebSocket handshake is rejected
        with client.websocket_connect("/ws/events") as ws:
            ws.send_json({"type": "auth", "token": "wrong-token"})
            err = ws.receive_json()
            assert err["type"] == "error"

        # Valid first-frame auth returns connected payload
        with client.websocket_connect("/ws/events") as ws:
            ws.send_json({"type": "auth", "token": container.api_token})
            msg = ws.receive_json()
            assert msg["type"] == "connected"
            assert "telemetry" in msg
            assert "security" in msg


def test_full_live_app_all_13_panels_and_ram_budget(tmp_path: Path) -> None:
    settings = AppSettings(ASPIRANT_DATA_DIR=tmp_path / "data")
    container = build_container(settings)
    app = create_app(settings=settings, container=container)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"

    try:
        for _ in range(60):
            try:
                if httpx.get(f"{base_url}/api/v1/health", timeout=0.3).status_code == 200:
                    break
            except Exception:
                time.sleep(0.05)

        qt = QApplication.instance() or QApplication([])
        api_client = AspirantApiClient(base_url=base_url, api_token=container.api_token)
        win = AspirantMainWindow(api_client=api_client)
        win.show()

        expected_types = {
            "home": HomeDashboardView,
            "voice": VoiceAssistantView,
            "chat": ChatView,
            "pc_control": PCControlView,
            "coding": CodingStudioView,
            "gov": GovServicesView,
            "video": VideoStudioView,
            "image": ImageStudioView,
            "files": FileManagerView,
            "memory": MemoryManagerView,
            "models": ModelsView,
            "security": SecurityCenterView,
            "settings": SettingsView,
        }
        assert len(NAV_SECTIONS) == 13
        for _grp, key, _label in NAV_SECTIONS:
            win.navigate_to(key)
            qt.processEvents()
            current_widget = win.stack.currentWidget()
            assert isinstance(current_widget, expected_types[key])

        QTimer.singleShot(500, win.close)
        qt.exec()

        rss_mb = psutil.Process().memory_info().rss / (1024 * 1024)
        # Keep memory footprint light for 8 GB RAM host (note: test runner also holds FastAPI/Test modules)
        assert rss_mb < 450.0
    finally:
        server.should_exit = True
        thread.join(timeout=2.5)
