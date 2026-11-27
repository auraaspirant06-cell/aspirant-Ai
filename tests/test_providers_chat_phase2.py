"""Phase 2 integration tests for MemoryStore, SecretVault, ProviderRegistry, and Chat API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncIterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fastapi.testclient import TestClient
from PySide6.QtWidgets import QApplication
import pytest

from aspirant.core.config import AppSettings
from aspirant.providers.base import (
    ChatRequest,
    ChatResponse,
    LLMProvider,
    ProviderHealth,
    StreamChunk,
)
from aspirant.server.app import build_container, create_app
from aspirant.ui.views.chat_view import ChatView


class _MockLLMProvider(LLMProvider):
    provider_id = "gemini"
    display_name = "Mock Gemini"
    default_model = "gemini-4-hydrogen"
    mode = "cloud"

    def __init__(self) -> None:
        self.last_request: ChatRequest | None = None

    def is_configured(self) -> bool:
        return True

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.provider_id,
            name=self.display_name,
            configured=True,
            healthy=True,
            latency_ms=12.0,
            detail="Mock connected",
            available_models=[self.default_model],
        )

    async def generate(self, request: ChatRequest) -> ChatResponse:
        self.last_request = request
        return ChatResponse(
            text=f"Namaste! Echo: {request.messages[-1].content}",
            provider=self.provider_id,
            model=self.default_model,
            input_tokens=20,
            output_tokens=15,
            latency_ms=25.0,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        self.last_request = request
        yield StreamChunk(delta_text="Namaste ", provider=self.provider_id, model=self.default_model)
        yield StreamChunk(delta_text="dost!", provider=self.provider_id, model=self.default_model)
        yield StreamChunk(
            delta_text="",
            done=True,
            provider=self.provider_id,
            model=self.default_model,
            input_tokens=18,
            output_tokens=10,
        )


def _make_test_app(tmp_path: Path):
    settings = AppSettings(ASPIRANT_DATA_DIR=tmp_path / "data")
    container = build_container(settings)
    mock = _MockLLMProvider()
    container.providers.register(mock)
    app = create_app(settings=settings, container=container)
    return TestClient(app), container, mock


def test_vault_and_memory_redaction_and_fts(tmp_path: Path) -> None:
    client, container, _ = _make_test_app(tmp_path)
    with client:
        container.vault.set_secret("GEMINI_API_KEY", "AIzaSyMockKey1234567890abcdefg")
        assert container.vault.get_secret("GEMINI_API_KEY") == "AIzaSyMockKey1234567890abcdefg"
        assert "GEMINI_API_KEY" in container.vault.list_secret_names()

        conv = container.memory.create_conversation(title="Python Async Help")
        container.memory.add_message(
            conv["id"],
            "user",
            "Learn FastAPI routing; my Aadhaar 2345 6789 0123 should vanish",
            language="en",
        )
        msgs = container.memory.get_messages(conv["id"])
        assert "2345 6789 0123" not in msgs[0]["content"]
        assert "[REDACTED_AADHAAR]" in msgs[0]["content"]

        hits = container.memory.search_messages("FastAPI")
        assert len(hits) == 1

        with pytest.raises(ValueError):
            container.memory.set_preference("my_api_key", "secret")


def test_chat_send_stream_persona_switch_and_network_gate(tmp_path: Path) -> None:
    client, container, mock = _make_test_app(tmp_path)
    headers = {"Authorization": f"Bearer {container.api_token}"}

    with client:
        # 1. Send Hinglish + persona switch request
        res = client.post(
            "/api/v1/chat/send",
            headers=headers,
            json={
                "message": "bhai switch to teacher mode aur python samjhao",
                "provider_id": "gemini",
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["persona"] == "teacher"
        assert body["switched_persona"] == "teacher"
        assert body["detected_language"]["code"] == "hinglish"
        assert "Teacher Mode" in (mock.last_request.system_instruction if mock.last_request else "")

        conv_id = body["conversation_id"]

        # 2. Stream SSE response on same conversation
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=headers,
            json={
                "message": "अगला चरण बताइए",
                "conversation_id": conv_id,
                "provider_id": "gemini",
            },
        ) as stream_resp:
            assert stream_resp.status_code == 200
            lines = [ln for ln in stream_resp.iter_lines() if ln.startswith("data: ")]
            assert any('"event": "delta"' in ln for ln in lines)
            assert any('"event": "done"' in ln for ln in lines)

        # 3. Verify usage ledger tracked both calls
        usage = client.get("/api/v1/providers/usage", headers=headers).json()["usage"]
        assert len(usage) >= 1

        # 4. Disabling NETWORK blocks cloud providers
        client.post(
            "/api/v1/system/permissions",
            headers=headers,
            json={"permission": "NETWORK", "granted": False},
        )
        blocked = client.post(
            "/api/v1/chat/send",
            headers=headers,
            json={"message": "hello", "provider_id": "gemini"},
        )
        assert blocked.status_code == 503


def test_configure_provider_endpoint_does_not_leak_secret(tmp_path: Path) -> None:
    client, container, _ = _make_test_app(tmp_path)
    headers = {"Authorization": f"Bearer {container.api_token}"}
    with client:
        secret_val = "AIzaSyFakeSecretValue1234567890"
        resp = client.post(
            "/api/v1/providers/configure",
            headers=headers,
            json={"key_name": "GEMINI_API_KEY", "value": secret_val},
        )
        assert resp.status_code == 200
        assert secret_val not in resp.text
        assert container.vault.get_secret("GEMINI_API_KEY") == secret_val


def test_chat_view_ui_instantiation() -> None:
    app = QApplication.instance() or QApplication([])

    class _StubClient:
        def list_conversations(self):
            return []

    view = ChatView(api_client=_StubClient())  # type: ignore[arg-type]
    assert view.persona_combo.count() == 7
    assert view.lang_combo.count() >= 19
    view.shutdown()
    app.processEvents()
