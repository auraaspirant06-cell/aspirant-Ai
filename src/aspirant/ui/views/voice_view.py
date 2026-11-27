"""Live Voice Assistant view: orb, Voice Control Dashboard, Mic Diagnostics Center, and First-Launch Setup Wizard."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QMetaObject, QObject, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QRadialGradient
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from aspirant.ui.client import AspirantApiClient
from aspirant.ui.theme import PALETTE
from aspirant.ui.widgets.glass import GlassCard, SectionHeader, StatusPill
from aspirant.voice.diagnostics import check_windows_mic_permission

_FIRST_LAUNCH_FLAG = Path(__file__).resolve().parents[4] / "data" / "first_launch_complete.json"


# ---------------------------------------------------------------------------
# Voice Orb
# ---------------------------------------------------------------------------

class VoiceOrbWidget(QWidget):
    """Animated neon-purple/cyan orb visualizing voice assistant state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(170, 170)
        self._state = "idle"
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_state(self, state: str) -> None:
        self._state = state
        self.update()

    def _tick(self) -> None:
        step = 0.14 if self._state in {"listening", "speaking"} else 0.04
        self._phase = (self._phase + step) % 6.283
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        import math

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        pulse = 0.5 + 0.5 * math.sin(self._phase)

        color_map = {
            "idle": QColor("#64748B"),
            "armed_wake_word": QColor(PALETTE["purple_bright"]),
            "listening": QColor(PALETTE["neon_cyan"]),
            "transcribing": QColor(PALETTE["blue"]),
            "thinking": QColor(PALETTE["amber"]),
            "speaking": QColor(PALETTE["emerald"]),
        }
        core_color = color_map.get(self._state, QColor(PALETTE["purple_bright"]))

        outer_radius = 60.0 + (12.0 * pulse if self._state != "idle" else 2.0 * pulse)
        grad = QRadialGradient(cx, cy, outer_radius)
        c_outer = QColor(core_color)
        c_outer.setAlpha(150)
        c_fade = QColor(core_color)
        c_fade.setAlpha(0)
        grad.setColorAt(0.0, c_outer)
        grad.setColorAt(0.65, QColor(core_color.red(), core_color.green(), core_color.blue(), 60))
        grad.setColorAt(1.0, c_fade)
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            int(cx - outer_radius),
            int(cy - outer_radius),
            int(outer_radius * 2),
            int(outer_radius * 2),
        )

        inner_r = 38.0 + (4.0 * pulse if self._state in {"listening", "speaking"} else 0.0)
        painter.setBrush(core_color)
        painter.drawEllipse(
            int(cx - inner_r),
            int(cy - inner_r),
            int(inner_r * 2),
            int(inner_r * 2),
        )
        painter.end()


# ---------------------------------------------------------------------------
# Background Workers
# ---------------------------------------------------------------------------

class _VoiceActionWorker(QObject):
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, client: AspirantApiClient) -> None:
        super().__init__()
        self.client = client
        self.kind = ""
        self.text = ""

    @Slot()
    def run(self) -> None:
        try:
            if self.kind == "speak":
                res = self.client.speak_voice_preview(self.text, play_locally=True)
            elif self.kind == "turn":
                res = self.client.send_voice_turn(self.text, speak_output=True)
            else:
                res = {}
            self.finished.emit(res)
        except Exception as exc:
            self.failed.emit(str(exc))


class _MicWorker(QObject):
    """Background worker for non-blocking mic discovery, testing, switching, and auto-recovery."""

    devices_ready = Signal(dict)
    test_ready = Signal(dict)
    recover_ready = Signal(dict)
    failed = Signal(str)

    def __init__(self, client: AspirantApiClient) -> None:
        super().__init__()
        self.client = client
        self.action = ""
        self.device_index: int | None = None

    @Slot()
    def run(self) -> None:
        try:
            if self.action == "devices":
                self.devices_ready.emit(self.client.get_mic_devices())
            elif self.action == "test":
                self.test_ready.emit(self.client.test_microphone(device_index=self.device_index))
            elif self.action == "change" and self.device_index is not None:
                res = self.client.change_microphone(self.device_index)
                self.devices_ready.emit(res)
            elif self.action == "recover":
                rec = self.client.recover_microphone()
                if rec.get("status") == "recovered":
                    # Fetch refreshed device list alongside recovery result
                    try:
                        rec["snapshot"] = self.client.get_mic_devices()
                    except Exception:
                        pass
                self.recover_ready.emit(rec)
        except Exception as exc:
            self.failed.emit(str(exc))


# ---------------------------------------------------------------------------
# First-Launch Setup Wizard
# ---------------------------------------------------------------------------

class MicSetupWizard(QDialog):
    """First-launch microphone setup wizard: check permissions, discover/select mic, auto-test, save."""

    def __init__(
        self,
        api_client: AspirantApiClient | None,
        parent: QWidget | None = None,
        *,
        auto_run: bool = True,
    ) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self._selected_device: dict[str, Any] = {}
        self._test_passed = False

        self.setWindowTitle("Microphone Setup Wizard — ASPIRANT AI")
        self.setMinimumWidth(560)
        self.setStyleSheet("background: #0F172A; color: #E2E8F0;")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 22, 24, 22)

        title = QLabel("🎤 First-Launch Microphone Setup Wizard")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #FFFFFF;")
        layout.addWidget(title)

        intro = QLabel(
            "ASPIRANT AI verifies microphone permissions, automatically picks your best microphone "
            "(USB / Bluetooth / Integrated), and tests live audio levels before first use."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 13px;")
        layout.addWidget(intro)

        self.perm_lbl = QLabel("1. Microphone Permission: Checking...")
        self.perm_lbl.setWordWrap(True)
        self.perm_lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(self.perm_lbl)

        self.grant_perm_btn = QPushButton("Open Windows Microphone Privacy & Enable Access")
        self.grant_perm_btn.setProperty("variant", "ghost")
        self.grant_perm_btn.clicked.connect(self._request_permissions)
        layout.addWidget(self.grant_perm_btn)

        self.device_combo = QComboBox()
        self.device_combo.setMinimumHeight(34)
        layout.addWidget(self.device_combo)

        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setValue(0)
        layout.addWidget(self.level_bar)

        self.result_lbl = QLabel("2. Microphone Auto-Test: Pending...")
        self.result_lbl.setWordWrap(True)
        self.result_lbl.setStyleSheet("font-size: 13px; color: #94A3B8;")
        layout.addWidget(self.result_lbl)

        btn_row = QHBoxLayout()
        self.test_btn = QPushButton("🎤 Auto-Test Microphone")
        self.test_btn.setProperty("variant", "primary")
        self.test_btn.clicked.connect(self._run_auto_check)
        btn_row.addWidget(self.test_btn)

        self.recover_btn = QPushButton("🔌 Auto-Recover Mic")
        self.recover_btn.setProperty("variant", "ghost")
        self.recover_btn.clicked.connect(self._run_recover)
        btn_row.addWidget(self.recover_btn)
        layout.addLayout(btn_row)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText("Complete Setup")
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self._on_reject)
        layout.addWidget(self._buttons)

        if auto_run:
            QTimer.singleShot(80, self._run_auto_check)

    def _request_permissions(self) -> None:
        QDesktopServices.openUrl(QUrl("ms-settings:privacy-microphone"))
        if self.api_client is not None:
            try:
                self.api_client.set_permission("READ", True)
            except Exception:
                pass
        self._run_auto_check()

    def _run_recover(self) -> None:
        if self.api_client is not None:
            try:
                self.api_client.recover_microphone()
            except Exception:
                pass
        self._run_auto_check()

    def _run_auto_check(self) -> None:
        perm = check_windows_mic_permission()
        if perm.get("granted", True):
            self.perm_lbl.setText("1. Microphone Permission: 🟢 Allowed (Windows & Desktop Apps)")
        else:
            self.perm_lbl.setText(f"1. Microphone Permission: 🔴 Denied — {perm.get('detail', '')}")

        if self.api_client is None:
            self.result_lbl.setText("2. Offline check complete (connect backend for hardware test).")
            self._test_passed = True
            return

        try:
            devices_data = self.api_client.get_mic_devices()
            self.device_combo.clear()
            for dev in devices_data.get("input_devices", []):
                lbl = f"{dev.get('display_name', dev['name'])} [{dev.get('device_type', 'unknown').upper()}]"
                self.device_combo.addItem(lbl, dev["index"])

            idx = self.device_combo.currentData()
            res = self.api_client.test_microphone(device_index=int(idx) if idx is not None else None)
            rms = float(res.get("rms_level", 0.0) or 0.0)
            pct = int(res.get("volume_percent", min(100, int(rms * 100))))
            qual = str(res.get("signal_quality", "unknown"))
            dev = res.get("best_device") or {}
            self._selected_device = dev
            name = dev.get("display_name") or dev.get("name") or "No Device"
            self.level_bar.setValue(pct)

            if res.get("device_opened"):
                emoji = "🟢"
                self._test_passed = True
                self.result_lbl.setText(
                    f"2. Auto-Test Passed: {emoji} {qual.upper()} | Mic: {name} | Level: {pct}% (RMS={rms:.4f})"
                )
            else:
                self._test_passed = False
                issues = "; ".join(res.get("issues", [])[:2])
                self.result_lbl.setText(
                    f"2. Attention Needed: 🔴 {qual.upper()} | Mic: {name} | {issues}"
                )
        except Exception as exc:
            self.result_lbl.setText(f"2. Check warning: {exc}")

    def _on_accept(self) -> None:
        try:
            _FIRST_LAUNCH_FLAG.parent.mkdir(parents=True, exist_ok=True)
            _FIRST_LAUNCH_FLAG.write_text(
                json.dumps(
                    {
                        "completed": True,
                        "device": self._selected_device.get("name", ""),
                        "sample_rate": self._selected_device.get("default_samplerate", 48000),
                        "test_passed": self._test_passed,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass
        self.accept()

    def _on_reject(self) -> None:
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            QMessageBox.warning(
                self,
                "Microphone Setup Incomplete",
                "Microphone setup was not finished. You can re-open the Setup Wizard anytime from Live Voice Assistant.",
            )
        self.reject()


# ---------------------------------------------------------------------------
# Voice Control Dashboard
# ---------------------------------------------------------------------------

class VoiceControlDashboard(QFrame):
    """Live dashboard displaying Listening, Wake Word, ASR, Voice Activity Meter, Noise Suppression, & Emoji status."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = GlassCard()
        outer.addWidget(card)

        hdr = QHBoxLayout()
        title = QLabel("🎛️ Voice Control Dashboard")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.conn_badge = StatusPill("🔴 Disconnected", "danger")
        self.state_badge = StatusPill("🎤 Idle", "muted")
        hdr.addWidget(title)
        hdr.addStretch(1)
        hdr.addWidget(self.state_badge)
        hdr.addWidget(self.conn_badge)
        card.body_layout.addLayout(hdr)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self._indicators: dict[str, QLabel] = {}
        pairs = [
            (0, 0, "listening_status", "Listening Status", "🎤 Idle"),
            (0, 2, "wake_word", "Wake Word Status", "🔴 Disconnected"),
            (1, 0, "asr_status", "Speech Recognition", "🟢 Ready"),
            (1, 2, "noise_suppression", "Noise Suppression", "🟢 ON (WebRTC VAD)"),
            (2, 0, "mic_device", "Active Microphone", "Scanning..."),
        ]
        for r, c, key, lbl_txt, default_val in pairs:
            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 12px;")
            val = QLabel(default_val)
            val.setWordWrap(True)
            val.setStyleSheet("font-size: 12px; font-weight: 600;")
            self._indicators[key] = val
            grid.addWidget(lbl, r, c)
            grid.addWidget(val, r, c + 1)

        vad_lbl = QLabel("Voice Activity Meter")
        vad_lbl.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 12px;")
        vad_box = QHBoxLayout()
        self.vad_meter = QProgressBar()
        self.vad_meter.setRange(0, 100)
        self.vad_meter.setValue(0)
        self.vad_meter.setFixedHeight(10)
        self.vad_meter.setTextVisible(False)
        self.vad_state_lbl = QLabel("🔇 Muted / Silent")
        self.vad_state_lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
        vad_box.addWidget(self.vad_meter, 1)
        vad_box.addWidget(self.vad_state_lbl)
        grid.addWidget(vad_lbl, 2, 2)
        grid.addLayout(vad_box, 2, 3)

        card.body_layout.addLayout(grid)

    def update_status(self, status: dict[str, Any]) -> None:
        if not status:
            return
        mic_ok = bool(status.get("mic_connected", False))
        muted = bool(status.get("muted", False))
        listening_mode = str(status.get("listening_mode", status.get("state", "idle")))
        wake_armed = bool(status.get("wake_word_armed", listening_mode == "wake_word"))
        vad_active = bool(status.get("vad_active", False))
        noise_on = bool(status.get("noise_suppression_on", True))
        asr_status = str(status.get("asr_status", "ready" if mic_ok else "unavailable"))
        pct = int(status.get("voice_activity_percent", 0))
        rms_db = status.get("rms_db", -90.0)

        if mic_ok:
            self.conn_badge.set_tone("ok", "🟢 Connected")
        else:
            self.conn_badge.set_tone("danger", "🔴 Disconnected")

        if muted:
            self.state_badge.set_tone("warn", "🔇 Muted")
            self._indicators["listening_status"].setText("🔇 Muted")
        elif listening_mode in {"listening", "transcribing", "hands_free", "push_to_talk"}:
            self.state_badge.set_tone("info", "🎤 Listening")
            self._indicators["listening_status"].setText(f"🎤 Listening ({listening_mode})")
        elif wake_armed:
            self.state_badge.set_tone("accent", '🎤 Armed ("Hey Aspirant")')
            self._indicators["listening_status"].setText('🎤 Listening (Wake Word Armed)')
        else:
            self.state_badge.set_tone("muted", "🎤 Ready")
            self._indicators["listening_status"].setText("🎤 Idle (On-Demand Ready)")

        self._indicators["wake_word"].setText(
            '🟢 Connected ("Hey Aspirant")' if wake_armed else "🔴 Disconnected"
        )
        self._indicators["asr_status"].setText(
            f"🔇 Muted" if muted else (f"🟢 {asr_status.title()}" if mic_ok else f"🔴 {asr_status.title()}")
        )
        self._indicators["noise_suppression"].setText(
            "🟢 Connected (WebRTC VAD)" if noise_on else "🔇 Muted (Off)"
        )

        dev_name = str(status.get("current_device_name") or "None")
        dev_type = str(status.get("current_device_type") or "")
        type_tag = f" [{dev_type.upper()}]" if dev_type else ""
        self._indicators["mic_device"].setText(
            f"🟢 {dev_name}{type_tag}" if mic_ok else "🔴 MIC: NOT FOUND"
        )

        self.vad_meter.setValue(0 if muted else max(0, min(100, pct)))
        if muted:
            self.vad_state_lbl.setText("🔇 Muted")
        elif vad_active:
            self.vad_state_lbl.setText(f"🎤 Listening ({pct}% • {rms_db} dB)")
        else:
            self.vad_state_lbl.setText(f"{pct}% ({rms_db} dB)" if pct > 0 else "🔇 Silent")


# ---------------------------------------------------------------------------
# Microphone Diagnostics Center Panel
# ---------------------------------------------------------------------------

class MicDiagnosticsPanel(QFrame):
    """Dedicated mic diagnostics panel displaying all metrics, selector, 5 actions, and auto-recovery."""

    mic_status_changed = Signal(bool, str, str)  # (mic_ok, device_name, device_type)

    def __init__(self, api_client: AspirantApiClient | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self._devices: list[dict[str, Any]] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = GlassCard()
        outer.addWidget(card)

        hdr = QHBoxLayout()
        title = QLabel("🎙️ Microphone Diagnostic Center")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.status_pill = StatusPill("CHECKING...", "muted")
        hdr.addWidget(title)
        hdr.addStretch(1)
        hdr.addWidget(self.status_pill)
        card.body_layout.addLayout(hdr)

        # Info grid displaying all 6 required items + Windows permission status
        info_grid = QGridLayout()
        info_grid.setSpacing(8)
        info_grid.setColumnStretch(1, 1)
        info_grid.setColumnStretch(3, 1)

        def _row(label: str, r: int, c: int) -> QLabel:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 12px;")
            val = QLabel("—")
            val.setWordWrap(True)
            val.setStyleSheet("font-size: 12px; font-weight: 600;")
            info_grid.addWidget(lbl, r, c)
            info_grid.addWidget(val, r, c + 1)
            return val

        self._name_val = _row("Connected Microphone:", 0, 0)
        self._device_status_val = _row("Device Status:", 0, 2)
        self._driver_val = _row("Driver Status:", 1, 0)
        self._rate_val = _row("Sample Rate:", 1, 2)
        self._test_val = _row("Test Result:", 2, 0)
        self._perm_val = _row("Windows Permission:", 2, 2)

        vol_lbl = QLabel("Input Volume Level:")
        vol_lbl.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 12px;")
        vol_wrap = QHBoxLayout()
        self._vol_bar = QProgressBar()
        self._vol_bar.setRange(0, 100)
        self._vol_bar.setValue(0)
        self._vol_bar.setFixedHeight(10)
        self._vol_bar.setTextVisible(False)
        self._vol_pct_lbl = QLabel("0%")
        self._vol_pct_lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
        vol_wrap.addWidget(self._vol_bar, 1)
        vol_wrap.addWidget(self._vol_pct_lbl)
        info_grid.addWidget(vol_lbl, 3, 0)
        info_grid.addLayout(vol_wrap, 3, 1, 1, 3)

        card.body_layout.addLayout(info_grid)

        # Device selector row
        sel_row = QHBoxLayout()
        sel_lbl = QLabel("Available Microphones:")
        sel_lbl.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 12px;")
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(260)
        self.device_combo.setPlaceholderText("Detecting USB / Bluetooth / Integrated / Virtual mics...")
        sel_row.addWidget(sel_lbl)
        sel_row.addWidget(self.device_combo, 1)
        card.body_layout.addLayout(sel_row)

        # 5 required action buttons in responsive 2-row grid so nothing clips on narrow screens
        btn_grid = QGridLayout()
        btn_grid.setSpacing(8)
        self.refresh_btn = QPushButton("Refresh Devices")
        self.refresh_btn.setProperty("variant", "ghost")
        self.test_btn = QPushButton("Test Microphone")
        self.test_btn.setProperty("variant", "primary")
        self.change_btn = QPushButton("Change Microphone")
        self.change_btn.setProperty("variant", "ghost")
        self.reconnect_btn = QPushButton("Reconnect Microphone")
        self.reconnect_btn.setProperty("variant", "ghost")
        self.troubleshoot_btn = QPushButton("Troubleshoot Audio")
        self.troubleshoot_btn.setProperty("variant", "ghost")

        btn_grid.addWidget(self.refresh_btn, 0, 0)
        btn_grid.addWidget(self.test_btn, 0, 1)
        btn_grid.addWidget(self.change_btn, 0, 2)
        btn_grid.addWidget(self.reconnect_btn, 1, 0)
        btn_grid.addWidget(self.troubleshoot_btn, 1, 1)
        card.body_layout.addLayout(btn_grid)

        self._issues_lbl = QLabel("")
        self._issues_lbl.setWordWrap(True)
        self._issues_lbl.setStyleSheet(f"color: {PALETTE['amber']}; font-size: 12px;")
        card.body_layout.addWidget(self._issues_lbl)

        self.refresh_btn.clicked.connect(self._refresh_devices)
        self.test_btn.clicked.connect(self._test_mic)
        self.change_btn.clicked.connect(self._change_mic)
        self.reconnect_btn.clicked.connect(self._reconnect)
        self.troubleshoot_btn.clicked.connect(self._troubleshoot)

        # Background worker thread
        self._thread = QThread(self)
        self._worker = _MicWorker(self.api_client)  # type: ignore[arg-type]
        self._worker.moveToThread(self._thread)
        self._worker.devices_ready.connect(self._on_devices)
        self._worker.test_ready.connect(self._on_test_result)
        self._worker.recover_ready.connect(self._on_recover)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

        # Automatic recovery timer: retry automatically on MIC NOT FOUND without restart
        self._recovery_attempts = 0
        self._recovery_timer = QTimer(self)
        self._recovery_timer.setInterval(4500)
        self._recovery_timer.timeout.connect(self._auto_recover_check)

    def _dispatch(self, action: str, device_index: int | None = None) -> None:
        if self.api_client is None:
            return
        self._worker.action = action
        self._worker.device_index = device_index
        QMetaObject.invokeMethod(self._worker, "run", Qt.ConnectionType.QueuedConnection)

    def _refresh_devices(self) -> None:
        self.status_pill.set_tone("muted", "SCANNING...")
        self._dispatch("devices")

    def _test_mic(self) -> None:
        self.status_pill.set_tone("accent", "TESTING MIC...")
        self.test_btn.setEnabled(False)
        idx = self.device_combo.currentData()
        self._dispatch("test", device_index=int(idx) if idx is not None else None)

    def _change_mic(self) -> None:
        idx = self.device_combo.currentData()
        if idx is not None:
            self.status_pill.set_tone("accent", "SWITCHING...")
            self._dispatch("change", device_index=int(idx))

    def _reconnect(self) -> None:
        self._recovery_attempts = 0
        self.status_pill.set_tone("accent", "RECONNECTING...")
        self._dispatch("recover")

    def _troubleshoot(self) -> None:
        QDesktopServices.openUrl(QUrl("ms-settings:privacy-microphone"))
        issues = self._issues_lbl.text()
        QMessageBox.information(
            self,
            "Audio Troubleshooting",
            (
                "Microphone Recovery & Troubleshooting Guide:\n\n"
                "1. Windows Settings -> Privacy & security -> Microphone -> Ensure desktop apps access is ON.\n"
                "2. Select a Windows WASAPI microphone in 'Available Microphones' above and click 'Change Microphone'.\n"
                "3. Verify physical mute switch / USB cable connection.\n"
                "4. Click 'Reconnect Microphone' to rescan audio subsystem and try alternates.\n\n"
                f"Current Diagnostics:\n{issues or 'All audio checks healthy.'}"
            ),
        )

    def _auto_recover_check(self) -> None:
        if self._recovery_attempts < 3:
            self._recovery_attempts += 1
            self.status_pill.set_tone("warn", f"AUTO-RECOVER ({self._recovery_attempts}/3)...")
            self._dispatch("recover")
        else:
            self._recovery_timer.stop()

    @Slot(dict)
    def _on_devices(self, data: dict[str, Any]) -> None:
        self._devices = data.get("input_devices", [])
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        selected_combo_idx = 0
        active = data.get("active_device") or data.get("best_device")
        active_idx = active.get("index") if active else None

        for i, dev in enumerate(self._devices):
            tag = f"{dev.get('device_type', 'unknown').upper()} • {dev.get('default_samplerate', 16000)}Hz"
            label = f"{dev.get('display_name', dev['name'])} [{tag}]"
            self.device_combo.addItem(label, dev["index"])
            if active_idx is not None and dev["index"] == active_idx:
                selected_combo_idx = i
        if self._devices:
            self.device_combo.setCurrentIndex(selected_combo_idx)
        self.device_combo.blockSignals(False)

        perm = data.get("permission", {})
        self._perm_val.setText(
            "🟢 Allowed" if perm.get("granted", True) else "🔴 Denied (Check Windows Settings)"
        )

        mic_ok = bool(data.get("mic_available", False))
        if mic_ok and active:
            dev_name = str(active.get("display_name") or active.get("name") or "Microphone")
            dev_type = str(active.get("device_type") or "unknown")
            self._name_val.setText(f"{dev_name} [{dev_type.upper()}]")
            self._device_status_val.setText("🟢 MIC: CONNECTED")
            self._driver_val.setText(str(active.get("driver_status", "Available")))
            self._rate_val.setText(f"{active.get('default_samplerate', 16000)} Hz")
            self.status_pill.set_tone("ok", "🟢 MIC: CONNECTED")
            self._recovery_timer.stop()
            self._recovery_attempts = 0
            self.mic_status_changed.emit(True, dev_name, dev_type)
        else:
            self._name_val.setText("No Openable Microphone Detected")
            self._device_status_val.setText("🔴 MIC: NOT FOUND (Diagnostics Running)")
            self._driver_val.setText("⚠️ Check Drivers / Permissions")
            self._rate_val.setText("—")
            self.status_pill.set_tone("danger", "🔴 MIC: NOT FOUND")
            if not self._recovery_timer.isActive():
                self._recovery_timer.start()
            self.mic_status_changed.emit(False, "", "")

        issues = data.get("issues_detected", [])
        guidance = data.get("repair_guidance", [])
        if issues:
            self._issues_lbl.setText(f"⚠️ {' | '.join(issues)}\n💡 {' | '.join(guidance[:2])}")
        elif guidance:
            self._issues_lbl.setStyleSheet(f"color: {PALETTE['emerald']}; font-size: 12px;")
            self._issues_lbl.setText(f"🟢 {guidance[0]}")

    @Slot(dict)
    def _on_test_result(self, data: dict[str, Any]) -> None:
        self.test_btn.setEnabled(True)
        rms = float(data.get("rms_level", 0.0) or 0.0)
        peak = float(data.get("peak_level", 0.0) or 0.0)
        db = data.get("db_level", -90.0)
        pct = int(data.get("volume_percent", min(100, int(rms * 100))))
        qual = str(data.get("signal_quality", "unknown"))

        self._vol_bar.setValue(max(0, min(100, pct)))
        self._vol_pct_lbl.setText(f"{pct}% ({db} dBFS)")

        if qual == "ok":
            self._test_val.setText(f"🟢 PASS (RMS={rms:.4f}, Peak={peak:.3f})")
            self.status_pill.set_tone("ok", "🟢 MIC TEST PASSED")
        elif qual == "quiet_ready":
            self._test_val.setText(f"🟢 READY / QUIET (RMS={rms:.5f}, {db} dBFS)")
            self.status_pill.set_tone("ok", "🟢 MIC READY (QUIET)")
        elif qual == "muted":
            self._test_val.setText("🔇 MUTED (Zero Input Signal)")
            self.status_pill.set_tone("warn", "🔇 MIC MUTED")
        elif qual == "clipping":
            self._test_val.setText(f"🔴 CLIPPING (Peak={peak:.3f})")
            self.status_pill.set_tone("danger", "🔴 CLIPPING")
        else:
            self._test_val.setText("🔴 UNAVAILABLE")
            self.status_pill.set_tone("danger", "🔴 MIC: NOT FOUND")

        issues = data.get("issues", [])
        if issues:
            self._issues_lbl.setStyleSheet(f"color: {PALETTE['amber']}; font-size: 12px;")
            self._issues_lbl.setText("⚠️ " + " | ".join(issues))

    @Slot(dict)
    def _on_recover(self, data: dict[str, Any]) -> None:
        status = data.get("status", "")
        dev = data.get("device")
        steps = data.get("steps_attempted", [])
        if status == "recovered" and dev:
            snap = data.get("snapshot")
            if isinstance(snap, dict):
                self._on_devices(snap)
            else:
                dev_name = str(dev.get("display_name") or dev.get("name") or "Microphone")
                dev_type = str(dev.get("device_type") or "unknown")
                self._name_val.setText(f"{dev_name} [{dev_type.upper()}]")
                self._device_status_val.setText("🟢 MIC: CONNECTED")
                self._driver_val.setText(str(dev.get("driver_status", "Recovered")))
                self._rate_val.setText(f"{dev.get('default_samplerate', 16000)} Hz")
                self.status_pill.set_tone("ok", "🟢 MIC: CONNECTED")
                self._recovery_timer.stop()
                self.mic_status_changed.emit(True, dev_name, dev_type)
            self._issues_lbl.setStyleSheet(f"color: {PALETTE['emerald']}; font-size: 12px;")
            self._issues_lbl.setText("✅ " + " → ".join(steps[-2:]) if steps else "✅ Microphone recovered.")
        else:
            self._device_status_val.setText("🔴 MIC: NOT FOUND")
            self.status_pill.set_tone("danger", "🔴 MIC: NOT FOUND")
            self._issues_lbl.setStyleSheet(f"color: {PALETTE['amber']}; font-size: 12px;")
            self._issues_lbl.setText(
                f"⚠️ {data.get('error', 'No devices available.')} ({' '.join(steps[-1:])})"
            )

    @Slot(str)
    def _on_failed(self, detail: str) -> None:
        self.test_btn.setEnabled(True)
        self.status_pill.set_tone("warn", "OFFLINE / RETRY")
        self._issues_lbl.setText(f"Diagnostics standby: {detail}")

    def start(self) -> None:
        """Scan microphones cleanly without interrupting UI."""
        self._refresh_devices()

    def shutdown(self) -> None:
        self._recovery_timer.stop()
        self._thread.quit()
        self._thread.wait(1000)


# ---------------------------------------------------------------------------
# Main Voice Assistant View
# ---------------------------------------------------------------------------

class VoiceAssistantView(QWidget):
    """Real-time female voice companion studio with Voice Control Dashboard & Mic Diagnostic Center."""

    run_action = Signal()
    mic_state_propagated = Signal(bool, str, str)

    def __init__(self, api_client: AspirantApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self._syncing = False
        self._muted = False

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        inner.setObjectName("ScrollContent")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(14)

        hdr_row = QHBoxLayout()
        self.header = SectionHeader(
            "Live Female Voice Assistant",
            'Wake word "Hey Aspirant" • Continuous & Push-to-Talk • 14+ Indian Languages • Barge-In',
            badge_text="IDLE",
            tone="muted",
        )
        self.wizard_btn = QPushButton("Mic Setup Wizard")
        self.wizard_btn.setProperty("variant", "ghost")
        self.wizard_btn.clicked.connect(self.open_setup_wizard)
        hdr_row.addWidget(self.header, 1)
        hdr_row.addWidget(self.wizard_btn)
        layout.addLayout(hdr_row)

        # Top Orb + Activation Controls
        hero = GlassCard()
        hero_row = QHBoxLayout()
        self.orb = VoiceOrbWidget()
        hero_row.addWidget(self.orb)

        ctrl_col = QVBoxLayout()
        ctrl_col.setSpacing(8)
        self.state_lbl = QLabel("Voice Engine State: Idle (On-Demand Ready)")
        self.state_lbl.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.privacy_lbl = QLabel(
            "Privacy Guarantee: Microphone opens only when you explicitly arm listening or run Mic Test."
        )
        self.privacy_lbl.setWordWrap(True)
        self.privacy_lbl.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 12px;")

        btn_grid = QGridLayout()
        btn_grid.setSpacing(8)
        self.wake_btn = QPushButton('Arm "Hey Aspirant"')
        self.wake_btn.setProperty("variant", "primary")
        self.wake_btn.clicked.connect(lambda: self._start_mode("wake_word"))

        self.ptt_btn = QPushButton("Push-to-Talk")
        self.ptt_btn.setProperty("variant", "ghost")
        self.ptt_btn.clicked.connect(lambda: self._start_mode("push_to_talk"))

        self.handsfree_btn = QPushButton("Continuous Listening")
        self.handsfree_btn.setProperty("variant", "ghost")
        self.handsfree_btn.clicked.connect(lambda: self._start_mode("hands_free"))

        self.live_btn = QPushButton("Gemini 3.8 Live")
        self.live_btn.setProperty("variant", "primary")
        self.live_btn.clicked.connect(lambda: self._start_mode("gemini_live"))

        self.mute_btn = QPushButton("🔇 Mute Mic")
        self.mute_btn.setProperty("variant", "ghost")
        self.mute_btn.clicked.connect(self._toggle_mute)

        self.interrupt_btn = QPushButton("Interrupt (Barge-In)")
        self.interrupt_btn.setProperty("variant", "ghost")
        self.interrupt_btn.clicked.connect(self._interrupt)

        self.stop_btn = QPushButton("Stop Mic")
        self.stop_btn.setProperty("variant", "danger")
        self.stop_btn.clicked.connect(self._stop_mode)

        controls = (
            self.wake_btn,
            self.ptt_btn,
            self.handsfree_btn,
            self.live_btn,
            self.mute_btn,
            self.interrupt_btn,
            self.stop_btn,
        )
        for idx, b in enumerate(controls):
            btn_grid.addWidget(b, idx // 4, idx % 4)

        ctrl_col.addWidget(self.state_lbl)
        ctrl_col.addWidget(self.privacy_lbl)
        ctrl_col.addLayout(btn_grid)
        hero_row.addLayout(ctrl_col, 1)
        hero.body_layout.addLayout(hero_row)
        layout.addWidget(hero)

        # Voice Control Dashboard
        self.voice_dashboard = VoiceControlDashboard()
        layout.addWidget(self.voice_dashboard)

        # Microphone Diagnostic Center
        self.mic_panel = MicDiagnosticsPanel(api_client)
        self.mic_panel.mic_status_changed.connect(self._on_mic_status_changed)
        layout.addWidget(self.mic_panel)

        # Female Voice Tuning & Provider Settings
        tuning = GlassCard()
        t_title = QLabel("Female Voice & Multilingual Speech Settings")
        t_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        tuning.body_layout.addWidget(t_title)

        grid = QGridLayout()
        grid.setSpacing(10)

        self.tts_combo = QComboBox()
        self.tts_combo.addItem("Auto (Gemini 3.8 TTS Primary -> Edge Neural)", "auto")
        self.tts_combo.addItem("Gemini 3.8 Flash TTS (Kore Female)", "gemini")
        self.tts_combo.addItem("Edge Female Neural (Free Indian Voices)", "edge-tts")
        self.tts_combo.addItem("Windows SAPI5 (Offline Female)", "sapi5")
        self.tts_combo.currentIndexChanged.connect(self._push_config)

        self.stt_combo = QComboBox()
        self.stt_combo.addItem("Auto (Gemini/Groq -> Local Whisper)", "auto")
        self.stt_combo.addItem("Gemini 3.5 Transcribe", "gemini")
        self.stt_combo.addItem("Groq Whisper", "groq")
        self.stt_combo.addItem("OpenAI Whisper", "openai")
        self.stt_combo.addItem("Local faster-whisper (Offline CPU)", "faster-whisper")
        self.stt_combo.currentIndexChanged.connect(self._push_config)

        self.emotion_combo = QComboBox()
        for emo in ("friendly", "cheerful", "calm", "professional", "empathetic", "neutral"):
            self.emotion_combo.addItem(emo.title(), emo)
        self.emotion_combo.currentIndexChanged.connect(self._push_config)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(75, 150)
        self.speed_slider.setValue(100)
        self.speed_slider.sliderReleased.connect(self._push_config)
        self.speed_lbl = QLabel("Speed: 1.00x")

        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setRange(-20, 20)
        self.pitch_slider.setValue(0)
        self.pitch_slider.sliderReleased.connect(self._push_config)
        self.pitch_lbl = QLabel("Pitch: +0 Hz")

        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_lbl.setText(f"Speed: {v / 100.0:.2f}x")
        )
        self.pitch_slider.valueChanged.connect(
            lambda v: self.pitch_lbl.setText(f"Pitch: {v:+d} Hz")
        )

        self.noise_chk = QCheckBox("Adaptive Background Noise Suppression (WebRTC VAD)")
        self.noise_chk.setChecked(True)
        self.noise_chk.toggled.connect(self._push_config)

        grid.addWidget(QLabel("Female TTS Provider:"), 0, 0)
        grid.addWidget(self.tts_combo, 0, 1)
        grid.addWidget(QLabel("Speech Recognition:"), 0, 2)
        grid.addWidget(self.stt_combo, 0, 3)

        grid.addWidget(QLabel("Voice Emotion:"), 1, 0)
        grid.addWidget(self.emotion_combo, 1, 1)
        grid.addWidget(self.speed_lbl, 1, 2)
        grid.addWidget(self.speed_slider, 1, 3)

        grid.addWidget(self.pitch_lbl, 2, 0)
        grid.addWidget(self.pitch_slider, 2, 1)
        grid.addWidget(self.noise_chk, 2, 2, 1, 2)
        tuning.body_layout.addLayout(grid)
        layout.addWidget(tuning)

        # Speak Test & Transcript Box
        test_card = GlassCard()
        test_hdr = QHBoxLayout()
        test_lbl = QLabel("Test Female Voice / Simulated Spoken Turn")
        test_lbl.setStyleSheet("font-size: 14px; font-weight: 700;")
        self.voice_feedback_pill = StatusPill("READY", "info")
        test_hdr.addWidget(test_lbl)
        test_hdr.addStretch(1)
        test_hdr.addWidget(self.voice_feedback_pill)
        test_card.body_layout.addLayout(test_hdr)

        input_row = QHBoxLayout()
        self.test_input = QLineEdit()
        self.test_input.setPlaceholderText(
            "Type Hindi/English/Hinglish text to hear female voice or run a full spoken turn..."
        )
        self.speak_btn = QPushButton("Speak Text (Female Voice)")
        self.speak_btn.setProperty("variant", "ghost")
        self.speak_btn.clicked.connect(self._speak_test)

        self.turn_btn = QPushButton("Ask & Speak Reply")
        self.turn_btn.setProperty("variant", "primary")
        self.turn_btn.clicked.connect(self._voice_turn_test)

        input_row.addWidget(self.test_input, 1)
        input_row.addWidget(self.speak_btn)
        input_row.addWidget(self.turn_btn)
        test_card.body_layout.addLayout(input_row)

        self.transcript_lbl = QLabel("Last Heard: --\nLast Spoken: --")
        self.transcript_lbl.setWordWrap(True)
        self.transcript_lbl.setProperty("role", "mono")
        test_card.body_layout.addWidget(self.transcript_lbl)
        layout.addWidget(test_card)
        layout.addStretch(1)

        scroll.setWidget(inner)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

        self._thread = QThread(self)
        self._worker = _VoiceActionWorker(self.api_client)
        self._worker.moveToThread(self._thread)
        self.run_action.connect(self._worker.run)
        self._worker.finished.connect(self._on_action_done)
        self._worker.failed.connect(self._on_action_failed)
        self._thread.start()

        if api_client is not None:
            self.mic_panel.start()

    def open_setup_wizard(self) -> None:
        wizard = MicSetupWizard(self.api_client, self, auto_run=True)
        wizard.exec()
        if self.api_client is not None:
            self.mic_panel.start()

    @Slot(bool, str, str)
    def _on_mic_status_changed(self, mic_ok: bool, device_name: str, device_type: str) -> None:
        self.voice_dashboard.update_status(
            {
                "mic_connected": mic_ok,
                "current_device_name": device_name or "None",
                "current_device_type": device_type,
                "listening_mode": "idle",
                "wake_word_armed": False,
                "asr_status": "ready" if mic_ok else "unavailable",
                "vad_active": False,
                "noise_suppression_on": self.noise_chk.isChecked(),
                "muted": self._muted,
            }
        )
        self.mic_state_propagated.emit(mic_ok, device_name, device_type)

    def _toggle_mute(self) -> None:
        self._muted = not self._muted
        self.mute_btn.setText("🎤 Unmute Mic" if self._muted else "🔇 Mute Mic")
        if self.api_client is not None:
            try:
                st = self.api_client.set_voice_muted(self._muted)
                self.update_status(st)
                return
            except Exception:
                pass
        self.voice_dashboard.update_status({"muted": self._muted, "mic_connected": True})

    def _start_mode(self, mode: str) -> None:
        try:
            st = self.api_client.start_voice_mode(mode)
            self.update_status(st)
        except Exception as exc:
            self.voice_feedback_pill.set_tone("danger", "BLOCKED")
            self.state_lbl.setText(f"Could not start voice mode: {exc}")

    def _stop_mode(self) -> None:
        try:
            st = self.api_client.stop_voice_mode()
            self.update_status(st)
        except Exception:
            pass

    def _interrupt(self) -> None:
        try:
            self.api_client.interrupt_voice()
            self.voice_feedback_pill.set_tone("warn", "INTERRUPTED")
        except Exception:
            pass

    def _push_config(self) -> None:
        if self._syncing:
            return
        try:
            self.api_client.update_voice_config(
                tts_provider=self.tts_combo.currentData(),
                stt_provider=self.stt_combo.currentData(),
                emotion=self.emotion_combo.currentData(),
                speed=round(self.speed_slider.value() / 100.0, 2),
                pitch_hz=self.pitch_slider.value(),
                noise_suppression=self.noise_chk.isChecked(),
            )
            self.voice_feedback_pill.set_tone("ok", "SAVED")
        except Exception as exc:
            self.voice_feedback_pill.set_tone("danger", "ERROR")
            self.voice_feedback_pill.setToolTip(str(exc))

    def _speak_test(self) -> None:
        txt = self.test_input.text().strip()
        if not txt:
            return
        self.speak_btn.setEnabled(False)
        self.voice_feedback_pill.set_tone("accent", "SYNTHESIZING...")
        self._worker.kind = "speak"
        self._worker.text = txt
        self.run_action.emit()

    def _voice_turn_test(self) -> None:
        txt = self.test_input.text().strip()
        if not txt:
            return
        self.turn_btn.setEnabled(False)
        self.voice_feedback_pill.set_tone("accent", "THINKING + SPEAKING...")
        self._worker.kind = "turn"
        self._worker.text = txt
        self.run_action.emit()

    @Slot(dict)
    def _on_action_done(self, res: dict[str, Any]) -> None:
        self.speak_btn.setEnabled(True)
        self.turn_btn.setEnabled(True)
        self.voice_feedback_pill.set_tone(
            "ok", f"DONE ({res.get('provider', res.get('tts', {}).get('provider', 'ok'))})"
        )
        if "reply" in res:
            self.transcript_lbl.setText(
                f"Last Heard: {res.get('transcript', '')}\nLast Spoken: {res.get('reply', '')}"
            )

    @Slot(str)
    def _on_action_failed(self, detail: str) -> None:
        self.speak_btn.setEnabled(True)
        self.turn_btn.setEnabled(True)
        self.voice_feedback_pill.set_tone("danger", "FAILED")
        self.transcript_lbl.setText(f"Voice error: {detail}")

    def update_status(self, status: dict[str, Any]) -> None:
        if not status:
            return
        state = str(status.get("state", "idle"))
        self.orb.set_state(state)
        state_labels = {
            "idle": ("Idle (On-Demand Ready)", "muted"),
            "armed_wake_word": ('Armed — Say "Hey Aspirant"', "accent"),
            "listening": ("Listening Continuously...", "info"),
            "transcribing": ("Transcribing Speech...", "info"),
            "thinking": ("Thinking...", "warn"),
            "speaking": ("Speaking (Female Neural Voice)...", "ok"),
        }
        label, tone = state_labels.get(state, (state.title(), "info"))
        self.header.badge.set_tone(tone, state.upper())
        self.state_lbl.setText(f"Voice Engine State: {label}")

        last_t = status.get("last_transcript") or "--"
        last_r = status.get("last_reply") or "--"
        if last_t != "--" or last_r != "--":
            self.transcript_lbl.setText(f"Last Heard: {last_t}\nLast Spoken: {last_r}")

        self.voice_dashboard.update_status(status)

    def shutdown(self) -> None:
        self.mic_panel.shutdown()
        self._thread.quit()
        self._thread.wait(1200)
