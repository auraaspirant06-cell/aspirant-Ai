"""Authenticated HTTP client for communication between PySide6 UI and FastAPI core."""

from __future__ import annotations

import json
from typing import Any, Iterator

import httpx


class AspirantApiClient:
    """Thread-safe REST + SSE client targeting the local loopback FastAPI daemon."""

    def __init__(self, base_url: str, api_token: str, timeout: float = 12.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self._headers = {"Authorization": f"Bearer {api_token}"}

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, headers=self._headers, timeout=self.timeout) as client:
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

    def get_overview(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/system/overview")

    def get_audit_logs(self, limit: int = 40, category: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if category and category != "all":
            params["category"] = category
        return self._request("GET", "/api/v1/audit/logs", params=params)

    def set_permission(self, permission: str, granted: bool) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/system/permissions",
            json={"permission": permission, "granted": granted},
        )

    def set_restricted_mode(self, enabled: bool) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/system/restricted-mode",
            json={"enabled": enabled},
        )

    def trigger_emergency_stop(self, reason: str = "User triggered Emergency STOP") -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/system/emergency-stop",
            json={"reason": reason},
        )

    def resume_system(self) -> dict[str, Any]:
        return self._request("POST", "/api/v1/system/resume")

    def check_provider_health(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/providers/health")

    def configure_provider_key(self, key_name: str, value: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/providers/configure",
            json={"key_name": key_name, "value": value},
        )

    def list_conversations(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/chat/conversations").get("items", [])

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/chat/conversations/{conversation_id}")

    def create_conversation(self, persona: str = "professional") -> dict[str, Any]:
        return self._request("POST", "/api/v1/chat/conversations", json={"persona": persona})

    def delete_conversation(self, conversation_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/api/v1/chat/conversations/{conversation_id}")

    def get_voice_status(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/voice/status")

    def update_voice_config(self, **updates: Any) -> dict[str, Any]:
        return self._request("POST", "/api/v1/voice/config", json=updates)

    def start_voice_mode(self, mode: str) -> dict[str, Any]:
        return self._request("POST", "/api/v1/voice/start", json={"mode": mode})

    def stop_voice_mode(self) -> dict[str, Any]:
        return self._request("POST", "/api/v1/voice/stop")

    def interrupt_voice(self) -> dict[str, Any]:
        return self._request("POST", "/api/v1/voice/interrupt")

    def speak_voice_preview(self, text: str, play_locally: bool = True) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/voice/speak",
            json={"text": text, "language_code": "auto", "play_locally": play_locally},
            timeout=35.0,
        )

    def send_voice_turn(self, transcript: str, speak_output: bool = True) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/voice/turn",
            json={"transcript": transcript, "speak_output": speak_output},
            timeout=45.0,
        )

    def list_apps(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/pc/apps").get("apps", [])

    def open_app(self, app_id: str) -> dict[str, Any]:
        return self._request("POST", "/api/v1/pc/apps/open", json={"app_id": app_id})

    def open_settings_page(self, page_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/pc/settings/{page_id}")

    def capture_screen(self) -> dict[str, Any]:
        return self._request("POST", "/api/v1/pc/screen/capture")

    def analyze_screen(self, question: str) -> dict[str, Any]:
        return self._request("POST", "/api/v1/pc/screen/analyze", json={"question": question}, timeout=45.0)

    def run_terminal_command(self, command: str, approval_id: str | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/pc/terminal/run",
            json={"command": command, "approval_id": approval_id},
            timeout=35.0,
        )

    def list_approvals(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/approvals").get("items", [])

    def decide_approval(self, approval_id: str, approve: bool) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/approvals/{approval_id}", json={"approve": approve})

    def browser_open(self, url: str) -> dict[str, Any]:
        return self._request("POST", "/api/v1/pc/browser/open", json={"url": url}, timeout=30.0)

    def browser_tabs(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/pc/browser/tabs").get("tabs", [])

    def files_list(self, path: str) -> dict[str, Any]:
        return self._request("GET", "/api/v1/files/list", params={"path": path})

    def files_search(self, root: str, pattern: str) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/files/search", params={"root": root, "pattern": pattern}).get("items", [])

    def files_read(self, path: str) -> dict[str, Any]:
        return self._request("GET", "/api/v1/files/read", params={"path": path})

    def files_write(self, path: str, content: str, overwrite: bool = False) -> dict[str, Any]:
        return self._request("POST", "/api/v1/files/write", json={"path": path, "content": content, "overwrite": overwrite})

    def files_move(self, src: str, dst: str) -> dict[str, Any]:
        return self._request("POST", "/api/v1/files/move", json={"src": src, "dst": dst})

    def files_trash(self, path: str) -> dict[str, Any]:
        return self._request("POST", "/api/v1/files/trash", json={"path": path})

    def files_organize(self, directory: str, dry_run: bool = True) -> dict[str, Any]:
        return self._request("POST", "/api/v1/files/organize", json={"directory": directory, "dry_run": dry_run})

    def stream_chat(
        self,
        message: str,
        conversation_id: str | None = None,
        persona_id: str = "professional",
        provider_id: str = "auto",
        language_override: str = "auto",
    ) -> Iterator[dict[str, Any]]:
        payload = {
            "message": message,
            "conversation_id": conversation_id,
            "persona_id": persona_id,
            "provider_id": provider_id,
            "language_override": language_override,
        }
        with httpx.Client(base_url=self.base_url, headers=self._headers, timeout=60.0) as client:
            with client.stream("POST", "/api/v1/chat/stream", json=payload) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line.startswith("data: "):
                        yield json.loads(line.removeprefix("data: "))
