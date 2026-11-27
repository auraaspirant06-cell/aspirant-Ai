"""Headless PySide6 UI smoke & interaction tests for Phase 1."""

from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from aspirant.ui.app_window import NAV_SECTIONS, AspirantMainWindow


class _FakeApiClient:
    """In-memory stub client simulating the FastAPI backend for deterministic UI tests."""

    def __init__(self) -> None:
        self.restricted = False
        self.stopped = False
        self.perms = {
            "READ": True,
            "WRITE": False,
            "EXECUTE": False,
            "BROWSER": False,
            "ADMIN": False,
            "NETWORK": True,
        }
        self.logs = [
            {
                "id": 1,
                "timestamp": "2026-11-26T08:30:00+00:00",
                "category": "system",
                "action": "ASPIRANT AI core service started",
                "permission": "READ",
                "decision": "started",
                "status": "ok",
            }
        ]

    def get_overview(self) -> dict[str, Any]:
        return {
            "app": "ASPIRANT AI",
            "version": "0.1.0",
            "active_task": "HALTED" if self.stopped else "Idle — Ready",
            "ram_budget_mb": 320,
            "data_dir": "C:\\Users\\harsh\\Documents\\AspirantAI\\data",
            "telemetry": {
                "cpu_percent": 14.5,
                "cpu_cores": 2,
                "cpu_threads": 4,
                "ram_percent": 65.0,
                "ram_used_mb": 5200,
                "ram_available_mb": 2600,
                "ram_total_mb": 7800,
                "app_ram_mb": 145.0,
                "disk_free_gb": 323.0,
                "disk_total_gb": 467.0,
                "disk_percent": 31.0,
                "net_rx_kbps": 12.3,
                "net_tx_kbps": 4.1,
                "audio": {
                    "mic_available": True,
                    "speaker_available": True,
                    "mic_count": 2,
                    "speaker_count": 2,
                },
            },
            "security": {
                "permissions": dict(self.perms),
                "restricted_mode": self.restricted,
                "emergency_stop_active": self.stopped,
            },
            "providers": [
                {
                    "id": "gemini",
                    "name": "Google Gemini",
                    "role": "Primary LLM",
                    "configured": False,
                    "mode": "cloud",
                }
            ],
        }

    def get_audit_logs(self, limit: int = 40, category: str | None = None) -> dict[str, Any]:
        items = self.logs
        if category and category != "all":
            items = [item for item in items if item["category"] == category]
        return {"items": items[:limit], "count": len(items)}

    def set_permission(self, permission: str, granted: bool) -> dict[str, Any]:
        self.perms[permission] = granted
        return {"permissions": dict(self.perms)}

    def set_restricted_mode(self, enabled: bool) -> dict[str, Any]:
        self.restricted = enabled
        return {"restricted_mode": self.restricted}

    def trigger_emergency_stop(self, reason: str = "UI") -> dict[str, Any]:
        self.stopped = True
        return {"emergency_stop_active": True}

    def resume_system(self) -> dict[str, Any]:
        self.stopped = False
        return {"emergency_stop_active": False}


def test_main_window_navigation_and_controls() -> None:
    app = QApplication.instance() or QApplication([])
    client = _FakeApiClient()
    window = AspirantMainWindow(api_client=client)  # type: ignore[arg-type]

    # Sync state immediately as if the poll returned
    overview = client.get_overview()
    logs = client.get_audit_logs()["items"]
    window._on_backend_data(overview, logs)

    assert len(window._view_indices) == 13
    for _group, key, _label in NAV_SECTIONS:
        window.navigate_to(key)
        assert window.stack.currentIndex() == window._view_indices[key]

    # Exercise Security controls end-to-end through UI slots
    window._set_permission("WRITE", True)
    assert client.perms["WRITE"] is True

    window._set_restricted_mode(True)
    assert client.restricted is True

    window._trigger_emergency_stop()
    assert client.stopped is True

    window._resume_system()
    assert client.stopped is False

    window.close()
    app.processEvents()
