"""Phase 1 integration tests for the FastAPI control plane."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aspirant.core.config import AppSettings
from aspirant.server.app import build_container, create_app


def _make_client(tmp_path: Path) -> tuple[TestClient, str]:
    settings = AppSettings(ASPIRANT_DATA_DIR=tmp_path / "data")
    container = build_container(settings)
    app = create_app(settings=settings, container=container)
    return TestClient(app), container.api_token


def test_health_is_accessible_and_protected_routes_require_token(tmp_path: Path) -> None:
    client, token = _make_client(tmp_path)
    with client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        unauth = client.get("/api/v1/system/overview")
        assert unauth.status_code == 401

        auth = client.get(
            "/api/v1/system/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert auth.status_code == 200
        payload = auth.json()
        assert "telemetry" in payload
        assert "security" in payload
        assert "providers" in payload


def test_host_and_origin_headers_are_enforced(tmp_path: Path) -> None:
    client, token = _make_client(tmp_path)
    with client:
        bad_origin = client.get(
            "/api/v1/health",
            headers={"Origin": "https://attacker.example"},
        )
        assert bad_origin.status_code == 403

        bad_host = client.get(
            "/api/v1/system/overview",
            headers={"Authorization": f"Bearer {token}", "Host": "evil.com"},
        )
        assert bad_host.status_code == 403


def test_permissions_restricted_and_emergency_stop_endpoints(tmp_path: Path) -> None:
    client, token = _make_client(tmp_path)
    headers = {"Authorization": f"Bearer {token}"}
    with client:
        r1 = client.post(
            "/api/v1/system/permissions",
            headers=headers,
            json={"permission": "WRITE", "granted": True},
        )
        assert r1.status_code == 200
        assert r1.json()["permissions"]["WRITE"] is True

        r2 = client.post(
            "/api/v1/system/restricted-mode",
            headers=headers,
            json={"enabled": True},
        )
        assert r2.status_code == 200
        assert r2.json()["restricted_mode"] is True

        r3 = client.post(
            "/api/v1/system/emergency-stop",
            headers=headers,
            json={"reason": "API test stop"},
        )
        assert r3.status_code == 200
        assert r3.json()["emergency_stop_active"] is True

        r4 = client.post("/api/v1/system/resume", headers=headers)
        assert r4.status_code == 200
        assert r4.json()["emergency_stop_active"] is False

        logs = client.get("/api/v1/audit/logs?limit=20", headers=headers)
        assert logs.status_code == 200
        assert logs.json()["count"] >= 4
