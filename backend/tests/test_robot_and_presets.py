"""Backend tests for 3D Robot API sync, male/female voice presets, and 22-stack engineering plans."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.core.config import EcosystemSettings
from backend.app.main import create_app


def test_ecosystem_robot_presets_and_new_stacks(tmp_path) -> None:
    db_file = tmp_path / "test_robot.db"
    cfg = EcosystemSettings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{db_file.as_posix()}",
        vector_backend="memory",
        chroma_persist_dir=str(tmp_path / "chroma"),
    )
    app = create_app(cfg)
    with TestClient(app) as client:
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": "harsh.master@aspirant.ai",
                "password": "StrongPassword!2026",
                "full_name": "Harsh",
            },
        )
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r_state = client.get("/api/v1/robot/state")
        assert r_state.status_code == 200
        assert r_state.json()["wake_phrase"] == "Hey Baby"
        assert "CODING" in r_state.json()["supported_states"]

        r_set = client.post(
            "/api/v1/robot/state",
            json={"state": "SPEAKING", "speech_amplitude": 0.85, "voice_gender": "male"},
        )
        assert r_set.status_code == 200
        assert r_set.json()["state"] == "SPEAKING"
        assert r_set.json()["voice_gender"] == "male"

        presets = client.get("/api/v1/voice/presets")
        assert presets.status_code == 200
        genders = {p.get("gender") for p in presets.json()["presets"]}
        assert genders == {"female", "male"}

        for stack in ("SQL", "Swift", "Dart", "Shell", "PowerShell"):
            res = client.post(
                "/api/v1/agents/project/generate",
                headers=headers,
                json={"project_name": f"demo-{stack.lower()}", "stack": stack},
            )
            assert res.status_code == 200
            assert len(res.json()["deliverables"]) == 8

        devops = client.post(
            "/api/v1/agents/devops/plan",
            headers=headers,
            json={"app_name": "aspirant-web", "platform": "DigitalOcean"},
        )
        assert devops.status_code == 200
        assert devops.json()["platform"] == "DigitalOcean"
        assert devops.json()["confirmation_required"] is True
