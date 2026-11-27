"""End-to-end integration and unit tests for the Aspirant AI Ecosystem."""

from __future__ import annotations

import base64
import io
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.ai.vector_store import ChromaVectorStore, QdrantVectorStore
from backend.app.core.config import EcosystemSettings
from backend.app.main import create_app


def _make_settings(tmp_path: Path, *, rate_limit: int = 120) -> EcosystemSettings:
    db_file = tmp_path / "ecosystem_test.db"
    return EcosystemSettings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{db_file.as_posix()}",
        jwt_secret_key="test-jwt-secret-key-for-ecosystem-suite-2026",
        encryption_master_key="test-encryption-master-key-for-ecosystem-suite",
        redis_url="redis://127.0.0.1:6399/9",
        celery_task_always_eager=True,
        vector_backend="qdrant",
        chroma_persist_dir=str(tmp_path / "chroma"),
        rate_limit_requests=rate_limit,
        rate_limit_window_seconds=60,
        gemini_api_key="",
        openai_api_key="",
    )


def _register_and_headers(client: TestClient, email: str = "founder@aspirant.ai") -> tuple[dict, dict[str, str]]:
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPassword!2026",
            "full_name": "Harsh Aspirant",
            "device_name": "Workstation-1",
            "device_platform": "windows",
        },
    )
    assert res.status_code == 201, res.text
    payload = res.json()
    headers = {"Authorization": f"Bearer {payload['access_token']}"}
    return payload, headers


def test_alembic_initial_migration_applies_cleanly(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "alembic_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    command.upgrade(cfg, "head")

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    get_settings.cache_clear()
    expected = {
        "users",
        "refresh_sessions",
        "memories",
        "goals",
        "habits",
        "reminders",
        "notes",
        "agent_runs",
        "audit_logs",
    }
    assert expected.issubset(tables)


def test_auth_refresh_rotation_security_headers_and_audit(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    with TestClient(app) as client:
        reg, headers = _register_and_headers(client)
        assert client.get("/api/v1/health").json()["status"] == "ok"
        assert client.get("/api/v1/auth/me", headers=headers).json()["user"]["email"] == "founder@aspirant.ai"

        # Refresh token rotates cleanly and invalidates previous token
        old_refresh = reg["refresh_token"]
        r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert r1.status_code == 200
        assert r1.headers["x-content-type-options"] == "nosniff"
        assert r1.headers["x-frame-options"] == "DENY"
        new_refresh = r1.json()["refresh_token"]
        assert new_refresh != old_refresh

        reused = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert reused.status_code == 401

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "founder@aspirant.ai", "password": "StrongPassword!2026"},
        )
        assert login.status_code == 200
        audit_res = client.get(
            "/api/v1/security/audit-logs",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        assert audit_res.status_code == 200
        actions = [e["action"] for e in audit_res.json()["events"]]
        assert "auth.register" in actions
        assert "auth.login" in actions


def test_rate_limiter_enforces_limit(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path, rate_limit=3))
    with TestClient(app) as client:
        for _ in range(3):
            assert client.get("/api/v1/health").status_code == 200
        blocked = client.get("/api/v1/health")
        assert blocked.status_code == 429


def test_qdrant_and_chroma_vector_backends_work_directly(tmp_path: Path) -> None:
    qdrant = QdrantVectorStore(in_memory=True, collection_name="test_qdrant")
    qdrant.upsert(
        record_id="m1",
        user_id="u1",
        text="Aspirant AI uses PostgreSQL and Qdrant for hybrid semantic memory.",
        metadata={"layer": "knowledge"},
    )
    q_hits = qdrant.search(user_id="u1", query="PostgreSQL semantic memory", limit=3)
    assert q_hits and q_hits[0].id == "m1"

    chroma = ChromaVectorStore(persist_dir=str(tmp_path / "chroma_unit"), collection_name="test_chroma")
    chroma.upsert(
        record_id="c1",
        user_id="u1",
        text="MAX Android mobile companion syncs habits and notes offline.",
        metadata={"layer": "knowledge"},
    )
    c_hits = chroma.search(user_id="u1", query="Android offline habits", limit=3)
    assert c_hits and c_hits[0].id == "c1"


def test_memory_encryption_at_rest_and_cross_restart_persistence(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    secret_phrase = "Classified Launch Blueprint Alpha-774"
    app1 = create_app(settings)
    with TestClient(app1) as client1:
        _, headers = _register_and_headers(client1)
        stored = client1.post(
            "/api/v1/memory",
            headers=headers,
            json={
                "content": secret_phrase,
                "layer": "long_term",
                "source_app": "mj",
                "tags": ["blueprint", "launch"],
                "importance": 0.95,
            },
        )
        assert stored.status_code == 200

        # Verify DB file contains ciphertext, NOT plaintext
        with sqlite3.connect(tmp_path / "ecosystem_test.db") as conn:
            raw_rows = conn.execute("SELECT content_encrypted FROM memories").fetchall()
        assert raw_rows
        assert secret_phrase not in raw_rows[0][0]

        client1.post(
            "/api/v1/memory/rag/ingest",
            headers=headers,
            json={
                "title": "Architecture Spec",
                "content": "Aspirant AI connects NOVA desktop, MJ planner, and MAX mobile companion.",
            },
        )
        rag_ans = client1.post(
            "/api/v1/memory/rag/query",
            headers=headers,
            json={"question": "What connects NOVA desktop and MAX mobile?"},
        )
        assert rag_ans.status_code == 200
        assert rag_ans.json()["citations"]

    # Restart completely new app instance pointing at same DB
    app2 = create_app(settings)
    with TestClient(app2) as client2:
        login = client2.post(
            "/api/v1/auth/login",
            json={"email": "founder@aspirant.ai", "password": "StrongPassword!2026"},
        )
        headers2 = {"Authorization": f"Bearer {login.json()['access_token']}"}
        recalled = client2.get("/api/v1/memory/search", params={"q": "Blueprint"}, headers=headers2)
        assert recalled.status_code == 200
        assert any(secret_phrase in item["content"] for item in recalled.json()["results"])


def test_seven_collaborative_agents_and_nova_mj_max_products(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    with TestClient(app) as client:
        _, headers = _register_and_headers(client)

        # Multi-agent catalog & all-7 collaboration execution
        catalog = client.get("/api/v1/agents/catalog").json()["agents"]
        assert {a["role"] for a in catalog} == {
            "research",
            "automation",
            "coding",
            "content",
            "productivity",
            "planning",
            "support",
        }
        exec_res = client.post(
            "/api/v1/agents/execute",
            headers=headers,
            json={
                "objective": "Research, code API fix, automate browser test, write release note, schedule reminders",
                "source_app": "nova",
                "agents": [
                    "research",
                    "automation",
                    "coding",
                    "content",
                    "productivity",
                    "planning",
                    "support",
                ],
            },
        )
        assert exec_res.status_code == 200
        assert len(exec_res.json()["plan_steps"]) == 7

        # NOVA checks
        wake = client.post("/api/v1/nova/wake-word", json={"transcript": "Hey Nova open daily notes"})
        assert wake.status_code == 200 and wake.json()["detected"] is True

        clip = client.post(
            "/api/v1/nova/clipboard/analyze",
            headers=headers,
            json={"content": "def hello():\n    return 'world'"},
        )
        assert clip.json()["kind"] == "code"

        buf = io.BytesIO()
        Image.new("RGB", (120, 60), color=(14, 165, 233)).save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        ocr = client.post("/api/v1/nova/screen/ocr", headers=headers, json={"image_base64": b64})
        assert ocr.status_code == 200 and ocr.json()["width"] == 120

        blocked_cmd = client.post(
            "/api/v1/nova/command/evaluate",
            headers=headers,
            json={"command": "rm -rf /"},
        )
        assert blocked_cmd.json()["risk"] == "blocked"

        voice = client.post(
            "/api/v1/nova/voice/command",
            headers=headers,
            json={"transcript": "Hey Nova summarize my code plan"},
        )
        assert voice.status_code == 200 and voice.json()["run_id"]

        # MJ checks
        mj_chat = client.post(
            "/api/v1/mj/chat",
            headers=headers,
            json={"message": "Help me structure Q1 product milestones"},
        )
        assert mj_chat.status_code == 200 and mj_chat.json()["reply"]

        cal = client.post(
            "/api/v1/mj/calendar/analyze",
            headers=headers,
            json={
                "events": [
                    {"title": "Standup", "start": "09:00", "end": "09:30"},
                    {"title": "Design Sync", "start": "09:15", "end": "10:00"},
                ]
            },
        )
        assert cal.status_code == 200 and len(cal.json()["conflicts"]) == 1

        mj_plan = client.post(
            "/api/v1/mj/research/plan",
            headers=headers,
            json={"topic": "Launch Aspirant AI v2", "create_goal": True},
        )
        assert mj_plan.status_code == 200 and mj_plan.json()["goal_id"]

        # MAX checks
        habit = client.post(
            "/api/v1/productivity/habits",
            headers=headers,
            json={"title": "Deep Focus", "cadence": "daily"},
        ).json()
        client.post(
            "/api/v1/productivity/reminders",
            headers=headers,
            json={"title": "Review PR", "due_at": "2026-11-28T09:00:00Z"},
        )
        sync = client.post(
            "/api/v1/max/sync",
            headers=headers,
            json={
                "offline_notes": [{"title": "Idea", "content": "Offline Android voice memo. Second sentence."}],
                "habit_checkins": [habit["id"]],
            },
        )
        assert sync.status_code == 200
        sync_data = sync.json()
        assert sync_data["habits"][0]["streak"] == 1
        assert sync_data["notes"][0]["ai_summary"]

        plan = client.get("/api/v1/max/daily-plan", headers=headers)
        assert plan.status_code == 200 and plan.json()["focus_goals"]

        push = client.post(
            "/api/v1/max/push",
            headers=headers,
            json={"title": "MAX Alert", "body": "Habit streak preserved!"},
        )
        assert push.status_code == 200 and push.json()["status"] == "dispatched"
