"""Verification suite for Master Prompt upgrades: Hey Baby wake word, dual-gender voices, 3D robot, 22 stacks & Deployment Engine."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fastapi.testclient import TestClient
from PySide6.QtWidgets import QApplication

from aspirant.coding.generator import (
    SUPPORTED_CODE_LANGUAGES,
    build_project_blueprint,
    normalize_code_language,
)
from aspirant.core.config import AppSettings
from aspirant.deployment.planner import inspect_project_for_deployment, plan_deployment
from aspirant.deployment.ssh_verifier import verify_ssh_readiness
from aspirant.providers.gemini_provider import GEMINI_MODELS
from aspirant.robot import ROBOT_STATES, RobotAvatarController, compute_animation_frame
from aspirant.security.permissions import Permission
from aspirant.server.app import create_app
from aspirant.ui.views.coding_view import CodingStudioView
from aspirant.ui.views.home_view import HomeDashboardView
from aspirant.ui.views.voice_view import VoiceAssistantView
from aspirant.ui.widgets.robot_widget import Robot3DWidget
from aspirant.voice.profiles import (
    GEMINI_MALE_VOICES,
    MALE_NEURAL_VOICES,
    VoiceConfig,
    resolve_edge_voice,
    resolve_gemini_voice,
)
from aspirant.voice.wakeword import DEFAULT_WAKE_WORD, build_voice_confirmation, match_wake_word


def _get_qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_wake_word_hey_baby_and_configurable_phrases() -> None:
    assert DEFAULT_WAKE_WORD == "Hey Baby"
    matched, cmd = match_wake_word("Hey Baby, create a FastAPI service")
    assert matched is True
    assert "FastAPI" in cmd

    matched_only, empty_cmd = match_wake_word("Hey Baby")
    assert matched_only is True
    assert empty_cmd == ""
    assert build_voice_confirmation(empty_cmd) == "Yes, I'm listening. Tell me."

    matched_custom, custom_cmd = match_wake_word("Ok Jarvis open terminal", wake_phrase="Ok Jarvis")
    assert matched_custom is True
    assert custom_cmd == "open terminal"


def test_dual_gender_voices_and_config_defaults(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WAKE_WORD", "Hey Baby")
    monkeypatch.setenv("VOICE_GENDER", "male")
    cfg = AppSettings(ASPIRANT_DATA_DIR=tmp_path)
    assert cfg.wake_word == "Hey Baby"
    assert cfg.voice_gender == "male"
    assert cfg.enable_robot is True
    assert cfg.gemini_live_model == "gemini-3.8-live"
    assert cfg.gemini_image_model == "gemini-nano-banana-2.1"
    assert "gemini-4-hydrogen" in GEMINI_MODELS
    assert "gemini-3.8-flash" in GEMINI_MODELS

    assert resolve_edge_voice("hi", gender="male") == MALE_NEURAL_VOICES["hi"]
    assert resolve_edge_voice("en", gender="female") == "en-IN-NeerjaNeural"
    assert resolve_gemini_voice(gender="male") in GEMINI_MALE_VOICES
    vc = VoiceConfig()
    assert vc.wake_phrase == "Hey Baby"
    assert vc.voice_gender in {"female", "male"}


def test_3d_robot_state_controller_and_animation() -> None:
    controller = RobotAvatarController()
    assert set(ROBOT_STATES) == {
        "IDLE",
        "LISTENING",
        "THINKING",
        "SPEAKING",
        "CODING",
        "WORKING",
        "SUCCESS",
        "ERROR",
    }
    snap = controller.set_state("SPEAKING", "Answering Harsh", speech_amplitude=0.75)
    assert snap["state"] == "SPEAKING"
    assert snap["animation"]["mouth_open"] >= 0.75
    assert snap["animation"]["wave_bars_active"] is True

    frame_idle = compute_animation_frame("IDLE", phase=1.0, speech_amplitude=0.0)
    assert frame_idle["mouth_open"] < 0.2

    sync_snap = controller.sync_from_voice_state("listening")
    assert sync_snap["state"] == "LISTENING"


def test_new_languages_and_deployment_engine(tmp_path: Path) -> None:
    for lang in ("sql", "swift", "dart", "shell", "powershell"):
        assert lang in SUPPORTED_CODE_LANGUAGES
        bp = build_project_blueprint(project_name=f"demo-{lang}", stack=lang)
        assert bp["stack"] == lang
        assert len(bp["deliverables"]) == 8

    assert normalize_code_language("ps1") == "powershell"
    assert normalize_code_language("bash") == "shell"

    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("GEMINI_API_KEY=\n", encoding="utf-8")
    inspected = inspect_project_for_deployment(tmp_path)
    assert inspected["runtime"] == "python-fastapi"
    assert inspected["has_env_example"] is True

    for plat in ("Azure", "AWS", "Ubuntu VPS", "DigitalOcean", "Hetzner", "Kubernetes"):
        plan = plan_deployment(
            app_name="aspirant-demo",
            platform=plat,
            domain="demo.example.com",
            project_root=tmp_path,
        )
        assert plan["platform"] == plat
        assert plan["confirmation_required"] is True
        assert plan["deployment_executed"] is False
        assert plan["systemd_unit"]
        assert plan["rollback_commands"]
        assert "ufw" in " ".join(plan["ufw_commands"]).lower()

    ssh_check = verify_ssh_readiness(host="203.0.113.10", user="ubuntu", key_path="")
    assert ssh_check["ready"] is False
    assert "SSH_KEY_PATH is not configured." in ssh_check["issues"]


def test_desktop_api_robot_bootstrap_and_widgets(tmp_path: Path) -> None:
    app = create_app(AppSettings(ASPIRANT_DATA_DIR=tmp_path / "appdata"))
    token = app.state.container.api_token
    headers = {"Authorization": f"Bearer {token}"}
    perms = app.state.container.permissions
    perms.set_permission(Permission.WRITE, True, actor="test")

    with TestClient(app) as client:
        r_get = client.get("/api/v1/robot/state", headers=headers)
        assert r_get.status_code == 200
        assert r_get.json()["state"] == "IDLE"

        r_post = client.post(
            "/api/v1/robot/state",
            headers=headers,
            json={"state": "CODING", "status_text": "Generating SQL + Swift", "speech_amplitude": 0.4},
        )
        assert r_post.status_code == 200
        assert r_post.json()["state"] == "CODING"

        v_cfg = client.post(
            "/api/v1/voice/config",
            headers=headers,
            json={"voice_gender": "male", "wake_phrase": "Hey Baby"},
        )
        assert v_cfg.status_code == 200
        assert v_cfg.json()["config"]["voice_gender"] == "male"

        pre = client.post(
            "/api/v1/coding/deploy-preflight",
            headers=headers,
            json={"ssh_host": "198.51.100.4", "ssh_user": "ubuntu", "ssh_key_path": ""},
        )
        assert pre.status_code == 200
        assert pre.json()["ssh"]["ready"] is False

        boot_dir = tmp_path / "web_boot"
        boot = client.post(
            "/api/v1/coding/bootstrap",
            headers=headers,
            json={"target_dir": str(boot_dir), "project_name": "my-app", "stack": "fastapi"},
        )
        assert boot.status_code == 200
        assert boot.json()["status"] == "verified"
        assert (boot_dir / ".gitignore").is_file()
        assert (boot_dir / "src" / "main.py").is_file()

    # Verify Qt offscreen widgets render & expose upgraded controls
    app_qt = _get_qapp()
    rw = Robot3DWidget()
    rw.set_robot_state("LISTENING", speech_amplitude=0.5)
    rw.grab()
    assert rw.current_state == "LISTENING"
    rw.shutdown()
    rw.close()

    home = HomeDashboardView(lambda _v: None, lambda _k: None)
    assert home.robot_widget.current_state == "IDLE"
    home.robot_widget.shutdown()
    home.close()

    voice = VoiceAssistantView(api_client=None)  # type: ignore[arg-type]
    assert voice.wake_input.text() == "Hey Baby"
    assert voice.gender_combo.count() == 2
    voice.shutdown()
    voice.close()

    coding = CodingStudioView(api_client=None)  # type: ignore[arg-type]
    assert coding.platform_combo.count() >= 9
    assert coding.lang_combo.count() >= 27
    coding.close()
    app_qt.processEvents()
