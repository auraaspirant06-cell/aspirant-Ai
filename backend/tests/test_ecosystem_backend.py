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
    db_path = tmp_path / "nested" / "alembic_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    backend_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    root_ini = Path(__file__).resolve().parents[2] / "alembic.ini"

    # Must work directly from Config without overriding script_location
    cfg = Config(str(backend_ini))
    command.upgrade(cfg, "head")
    command.check(cfg)

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        rev = conn.execute("SELECT version_num FROM alembic_version").fetchone()

    assert rev == ("0002_voice_integrations_reasoning",)
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
        "voice_profiles",
        "social_connections",
        "feedback_events",
    }
    assert expected.issubset(tables)

    # Root alembic.ini must point to the exact same state
    root_cfg = Config(str(root_ini))
    command.check(root_cfg)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    get_settings.cache_clear()


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


def test_multilingual_voice_commands_and_speaker_identity(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    with TestClient(app) as client:
        _, headers = _register_and_headers(client, email="voice@aspirant.ai")

        langs = client.get("/api/v1/voice/languages").json()["languages"]
        assert len(langs) == 14

        samples_by_lang = {
            "hi": "मेरा आज का प्लान खोलो",
            "hinglish": "Bhai aaj ka schedule aur task batao",
            "en": "Open browser and check notes",
            "bn": "আমাকে বাংলায় সাহায্য করুন",
            "ta": "தமிழில் விளக்கவும்",
            "te": "తెలుగులో వివరించండి",
            "mr": "तुम्ही कसे आहात मला मराठीत सांगा",
            "gu": "મને ગુજરાતીમાં સમજાવો",
            "pa": "ਮੈਨੂੰ ਪੰਜਾਬੀ ਵਿੱਚ ਦੱਸੋ",
            "kn": "ಕನ್ನಡದಲ್ಲಿ ವಿವರಿಸಿ",
            "ml": "മലയാളത്തിൽ വിശദീകരിക്കൂ",
            "ur": "اردو میں سمجھائیں",
            "or": "ମୋତେ ଓଡ଼ିଆରେ ବୁଝାନ୍ତୁ",
            "as": "মই অসমীয়াত সহায় বিচাৰিছোঁ",
        }
        for code, text in samples_by_lang.items():
            res = client.post(
                "/api/v1/voice/process",
                headers=headers,
                json={"transcript": text, "far_field": True, "noise_db": -44.0},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["language"] == code
            assert data["confidence"] > 0.4

        # Speaker enrollment rejects invalid password fallback
        bad_enroll = client.post(
            "/api/v1/voice/identity/enroll",
            headers=headers,
            json={
                "password": "WrongPassword!",
                "label": "Owner",
                "samples": [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2] * 4,
                "voice_unlock_enabled": True,
            },
        )
        assert bad_enroll.status_code == 403

        owner_samples = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2] * 4
        ok_enroll = client.post(
            "/api/v1/voice/identity/enroll",
            headers=headers,
            json={
                "password": "StrongPassword!2026",
                "label": "Owner",
                "samples": owner_samples,
                "voice_unlock_enabled": True,
                "confidence_threshold": 0.9,
            },
        )
        assert ok_enroll.status_code == 200

        verified = client.post(
            "/api/v1/voice/identity/verify",
            headers=headers,
            json={"samples": owner_samples},
        )
        assert verified.json()["verified"] is True and verified.json()["access_level"] == "trusted"

        # Unrecognized voice restricts access & blocks sensitive delete command
        impostor_samples = [-0.1, 0.95, -0.85, 0.1, -0.9, 0.85, -0.2, 0.7] * 4
        blocked_voice = client.post(
            "/api/v1/voice/process",
            headers=headers,
            json={
                "transcript": "Delete project workspace files",
                "voice_samples": impostor_samples,
                "explicit_authorization": True,
            },
        )
        assert blocked_voice.status_code == 200
        assert blocked_voice.json()["access_level"] == "restricted"
        assert blocked_voice.json()["authorized"] is False


def test_reasoning_self_reflection_social_connectors_and_self_healing(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    with TestClient(app) as client:
        _, headers = _register_and_headers(client, email="intel@aspirant.ai")

        # Cross-session feedback learning + deep reasoning
        fb = client.post(
            "/api/v1/agents/feedback",
            headers=headers,
            json={
                "objective": "Design FastAPI deployment",
                "intent": "code_engineering",
                "rating": 2,
                "correction_note": "Always include Alembic migration step before Uvicorn startup",
            },
        )
        assert fb.status_code == 200 and fb.json()["learned_across_sessions"] is True

        reasoned = client.post(
            "/api/v1/agents/reason",
            headers=headers,
            json={"objective": "Plan Python FastAPI API release roadmap"},
        )
        assert reasoned.status_code == 200
        rdata = reasoned.json()
        assert rdata["reflection"]["passed"] is True
        assert any("Alembic" in lesson for lesson in rdata["prior_lessons_used"])

        # Social platform connectors (encrypted tokens, permission check, webhooks)
        secret_bot_token = "1234567890:SECRET_TELEGRAM_TOKEN_VALUE"
        conn = client.post(
            "/api/v1/integrations/connect",
            headers=headers,
            json={
                "platform": "telegram",
                "access_token": secret_bot_token,
                "permissions": ["read", "webhook"],
            },
        )
        assert conn.status_code == 200

        with sqlite3.connect(tmp_path / "ecosystem_test.db") as db:
            enc_rows = db.execute("SELECT access_token_encrypted FROM social_connections").fetchall()
        assert enc_rows and secret_bot_token not in enc_rows[0][0]

        denied_pub = client.post(
            "/api/v1/integrations/dispatch",
            headers=headers,
            json={"platform": "telegram", "permission": "publish", "payload": {"text": "hi"}},
        )
        assert denied_pub.status_code == 403

        webhook = client.post(
            "/api/v1/integrations/event",
            headers=headers,
            json={"platform": "telegram", "event": {"message": {"text": "Hey Nova!", "from": {"username": "harsh"}}}},
        )
        assert webhook.status_code == 200 and webhook.json()["sender"] == "harsh"

        # Self-healing repository audit + API contract check
        heal = client.get("/api/v1/self-healing/audit", headers=headers)
        assert heal.status_code == 200
        hdata = heal.json()
        assert hdata["overall_status"] in {"healthy", "repaired"}
        by_name = {c["name"]: c["status"] for c in hdata["checks"]}
        assert by_name["dependencies"] == "ok"
        assert by_name["alembic_paths"] == "ok"
        assert by_name["ui_routes"] == "ok"
        assert by_name["api_contracts"] == "ok"


def test_live_streaming_voice_presets_mic_windows_smart_memory_and_crash_recovery(
    tmp_path: Path,
) -> None:
    app = create_app(_make_settings(tmp_path))
    with TestClient(app) as client:
        _, headers = _register_and_headers(client, email="companion@aspirant.ai")

        # Voice presets, preview, mic diagnostics & consent-gated cloning hook
        presets = client.get("/api/v1/voice/presets").json()["presets"]
        assert len(presets) >= 4
        prev = client.post("/api/v1/voice/preview", json={"preset_id": "aanya-warm"})
        assert prev.status_code == 200 and prev.json()["ready"] is True

        mic = client.post(
            "/api/v1/voice/diagnostics/audio",
            headers=headers,
            json=[0.001, -0.001, 0.0005, -0.0005] * 4,
        )
        assert mic.status_code == 200 and mic.json()["repair_guidance"]

        clone_denied = client.post(
            "/api/v1/voice/clone/hook",
            headers=headers,
            json={
                "password": "StrongPassword!2026",
                "explicit_consent": False,
                "voice_name": "MyVoice",
                "reference_samples": [0.2, 0.4, -0.3, 0.1] * 4,
            },
        )
        assert clone_denied.status_code == 403

        clone_ok = client.post(
            "/api/v1/voice/clone/hook",
            headers=headers,
            json={
                "password": "StrongPassword!2026",
                "explicit_consent": True,
                "voice_name": "MyVoice",
                "reference_samples": [0.2, 0.4, -0.3, 0.1] * 4,
            },
        )
        assert clone_ok.status_code == 200 and clone_ok.json()["registered"] is True

        # Streaming SSE Live Companion mode
        stream = client.post(
            "/api/v1/voice/companion/stream",
            headers=headers,
            json={"transcript": "Bhai aaj ka weather aur goal plan batao"},
        )
        assert stream.status_code == 200
        assert "hinglish" in stream.text and '"done": true' in stream.text

        # Windows integration layer (search, organize dry-run & auth gate, notify, close gate)
        org_dir = tmp_path / "downloads_org"
        org_dir.mkdir()
        (org_dir / "notes.md").write_text("hello", encoding="utf-8")
        (org_dir / "photo.png").write_bytes(b"PNG")

        searched = client.post(
            "/api/v1/nova/windows/search-files",
            headers=headers,
            json={"query": "notes", "directory": str(org_dir)},
        )
        assert searched.status_code == 200 and searched.json()["matches"]

        org_blocked = client.post(
            "/api/v1/nova/windows/organize",
            headers=headers,
            json={"directory": str(org_dir), "dry_run": False, "authorized": False},
        )
        assert org_blocked.json()["requires_authorization"] is True

        org_ok = client.post(
            "/api/v1/nova/windows/organize",
            headers=headers,
            json={"directory": str(org_dir), "dry_run": False, "authorized": True},
        )
        assert org_ok.json()["applied"] is True and (org_dir / "Documents" / "notes.md").exists()

        win_close_gate = client.post(
            "/api/v1/nova/windows/manage",
            headers=headers,
            json={"action": "close", "title_query": "Notepad", "authorized": False},
        )
        assert win_close_gate.json()["requires_authorization"] is True

        # Smart memory action tracking + crash recovery journal endpoints
        client.post(
            "/api/v1/memory/actions/track",
            headers=headers,
            json={
                "action": "open_voice_companion",
                "workflow_name": "Morning Hinglish Briefing",
                "device_preferences": {"primary_mic": "Studio USB", "theme": "dark"},
            },
        )
        smart = client.get("/api/v1/memory/profile/smart", headers=headers)
        assert smart.status_code == 200
        sdata = smart.json()
        assert sdata["frequent_actions"]["open_voice_companion"] == 1
        assert "Morning Hinglish Briefing" in sdata["personalized_workflows"]
        assert sdata["device_preferences"]["primary_mic"] == "Studio USB"

        rec = client.post("/api/v1/self-healing/recover", headers=headers)
        assert rec.status_code == 200 and rec.json()["status"] == "recovered"


def test_microphone_detection_diagnostics_and_recovery(tmp_path: Path) -> None:
    """Microphone detection, device enumeration, mic test, and auto-recovery endpoints."""
    app = create_app(_make_settings(tmp_path))
    with TestClient(app) as client:
        _, headers = _register_and_headers(client, email="mic@aspirant.ai")

        # GET /voice/diagnostics/devices — full device list (may be empty on CI/headless)
        devices_res = client.get("/api/v1/voice/diagnostics/devices", headers=headers)
        assert devices_res.status_code == 200
        ddata = devices_res.json()
        assert "mic_available" in ddata
        assert "input_devices" in ddata
        assert "output_devices" in ddata
        assert "health_status" in ddata
        assert "issues_detected" in ddata
        assert "repair_guidance" in ddata
        # best_device may be None on CI — that's fine
        assert ddata["health_status"] in {"healthy", "attention_needed"}
        # repair_guidance must always be non-empty (healthy guidance or repair tips)
        assert isinstance(ddata["repair_guidance"], list) and len(ddata["repair_guidance"]) > 0

        # POST /voice/diagnostics/test-mic with dict payload & raw array payload
        samples = [0.05, -0.04, 0.06, -0.05] * 8
        test_res = client.post(
            "/api/v1/voice/diagnostics/test-mic",
            headers=headers,
            json={"samples": samples},
        )
        assert test_res.status_code == 200
        tdata = test_res.json()
        assert tdata["signal_quality"] in {"ok", "quiet_ready"}
        assert isinstance(tdata["rms_level"], float)
        assert "volume_percent" in tdata

        # True muted (all zeros) vs quiet-room thermal floor
        muted_res = client.post(
            "/api/v1/voice/diagnostics/test-mic",
            headers=headers,
            json=[0.0, 0.0, 0.0, 0.0] * 4,
        )
        assert muted_res.status_code == 200
        assert muted_res.json()["signal_quality"] == "muted"

        quiet_res = client.post(
            "/api/v1/voice/diagnostics/test-mic",
            headers=headers,
            json=[0.0001, -0.0001] * 16,
        )
        assert quiet_res.status_code == 200
        assert quiet_res.json()["signal_quality"] in {"muted", "quiet_ready", "ok"}

        if ddata["input_devices"]:
            target_idx = ddata["input_devices"][0]["index"]
            ch_res = client.post(
                "/api/v1/voice/diagnostics/change-mic",
                headers=headers,
                json={"device_index": target_idx},
            )
            assert ch_res.status_code == 200 and ch_res.json()["status"] == "changed"

        mute_res = client.post("/api/v1/voice/mute", headers=headers, json={"muted": True})
        assert mute_res.status_code == 200 and mute_res.json()["muted"] is True
        client.post("/api/v1/voice/mute", headers=headers, json={"muted": False})

        # POST /voice/diagnostics/recover — auto-recovery (returned status must be a known value)
        recover_res = client.post("/api/v1/voice/diagnostics/recover", headers=headers)
        assert recover_res.status_code == 200
        rdata = recover_res.json()
        assert rdata["status"] in {"recovered", "no_devices"}
        assert rdata["mic_status"] in {"MIC: CONNECTED", "MIC: NOT FOUND"}
        if rdata["status"] == "recovered":
            assert rdata["device"] is not None
            assert "name" in rdata["device"]
            assert "device_type" in rdata["device"]
        else:
            assert rdata["device"] is None or rdata["device"] == {}

        # GET /voice/status — full voice dashboard status
        status_res = client.get("/api/v1/voice/status", headers=headers)
        assert status_res.status_code == 200
        sdata = status_res.json()
        required_fields = {
            "listening_mode",
            "wake_word_armed",
            "asr_status",
            "vad_active",
            "voice_activity_percent",
            "noise_suppression_on",
            "muted",
            "mic_connected",
            "mic_status",
            "current_device_name",
            "current_device_type",
            "driver_status",
            "sample_rate",
            "health_status",
            "issues",
        }
        assert required_fields.issubset(sdata.keys())
        assert isinstance(sdata["mic_connected"], bool)
        assert isinstance(sdata["noise_suppression_on"], bool)
        assert sdata["health_status"] in {"healthy", "attention_needed"}

        # Confirm MIC NOT FOUND does NOT cause a 500 — always graceful
        # (this is the core requirement: never permanent error without diagnostics)
        assert status_res.status_code == 200  # already checked but make intent explicit


def test_system_prompt_wake_words_project_generator_devops_and_debugging(tmp_path: Path) -> None:
    """Verify Aspirant AI identity, wake words, 17-stack Project Generator, DevOps safety rule, Debug & Learning modes."""
    app = create_app(_make_settings(tmp_path))
    with TestClient(app) as client:
        _, headers = _register_and_headers(client, email="boss@aspirant.ai")

        for wake_text in (
            "Hey Aspirant, create a FastAPI project.",
            "Aspirant, explain Docker step by step.",
            "Hello Aspirant deploy this app",
        ):
            wres = client.post("/api/v1/nova/wake-word", json={"transcript": wake_text})
            assert wres.status_code == 200 and wres.json()["detected"] is True

        vcmd = client.post(
            "/api/v1/nova/voice/command",
            headers=headers,
            json={"transcript": "Hey Aspirant, create a FastAPI project."},
        )
        assert vcmd.status_code == 200 and "Boss" in vcmd.json()["confirmation"]

        proj = client.post(
            "/api/v1/agents/project/generate",
            headers=headers,
            json={"project_name": "Orders API", "stack": "Laravel"},
        )
        assert proj.status_code == 200
        pdata = proj.json()
        assert len(pdata["deliverables"]) == 8
        assert len(pdata["supported_stacks"]) == 17

        devops = client.post(
            "/api/v1/agents/devops/plan",
            headers=headers,
            json={"app_name": "orders", "platform": "AWS", "domain": "api.orders.dev", "execution_confirmed": False},
        )
        assert devops.status_code == 200
        ddata = devops.json()
        assert len(ddata["supported_platforms"]) == 9
        assert ddata["deployment_executed"] is False and ddata["confirmation_required"] is True

        dbg = client.post(
            "/api/v1/agents/debug",
            headers=headers,
            json={"error_log": "Traceback:\nModuleNotFoundError: No module named 'uvicorn'"},
        )
        assert dbg.status_code == 200
        assert dbg.json()["analyzed_first"] is True and dbg.json()["prevention_methods"]

        lrn = client.post(
            "/api/v1/agents/learn",
            headers=headers,
            json={"concept": "Reverse Proxy"},
        )
        assert lrn.status_code == 200
        assert lrn.json()["real_world_analogy"] and len(lrn.json()["step_by_step"]) >= 3
