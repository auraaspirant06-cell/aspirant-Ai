"""Unified desktop launcher starting the local FastAPI engine and PySide6 UI."""

from __future__ import annotations

import socket
import sys
import threading
import time

import httpx
from PySide6.QtWidgets import QApplication
import uvicorn

from aspirant import APP_NAME
from aspirant.core.config import AppSettings
from aspirant.server.app import build_container, create_app
from aspirant.ui.app_window import AspirantMainWindow
from aspirant.ui.client import AspirantApiClient


def _find_available_port(host: str, preferred_port: int) -> int:
    """Use preferred_port if free, otherwise select an available ephemeral loopback port."""
    for candidate in (preferred_port, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, candidate))
                return int(sock.getsockname()[1])
            except OSError:
                continue
    return preferred_port


def main() -> int:
    settings = AppSettings()
    port = _find_available_port(settings.host, settings.port)
    container = build_container(settings)
    fastapi_app = create_app(settings=settings, container=container)

    uv_config = uvicorn.Config(
        fastapi_app,
        host=settings.host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(uv_config)
    server_thread = threading.Thread(target=server.run, name="aspirant-api", daemon=True)
    server_thread.start()

    base_url = f"http://{settings.host}:{port}"
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{base_url}/api/v1/health", timeout=0.5)
            if resp.status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)

    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.setApplicationName(APP_NAME)
    client = AspirantApiClient(base_url=base_url, api_token=container.api_token)
    window = AspirantMainWindow(api_client=client)
    window.show()

    try:
        return int(qt_app.exec())
    finally:
        server.should_exit = True
        server_thread.join(timeout=3.0)


if __name__ == "__main__":
    raise SystemExit(main())
