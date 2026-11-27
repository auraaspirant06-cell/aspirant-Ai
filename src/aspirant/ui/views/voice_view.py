"""Live Voice Assistant view with animated voice orb, wake-word controls, and female voice tuning."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from aspirant.ui.client import AspirantApiClient
from aspirant.ui.theme import PALETTE
from aspirant.ui.widgets.glass import GlassCard, SectionHeader, StatusPill


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


class VoiceAssistantView(QWidget):
    """Real-time female voice companion studio with wake-word, PTT, and prosody tuning."""

    run_action = Signal()

    def __init__(self, api_client: AspirantApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self._syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(14)

        self.header = SectionHeader(
            "Live Female Voice Assistant",
            'Wake word "Hey Aspirant" • Push-to-Talk • Hands-free • Instant barge-in interruption',
            badge_text="IDLE",
            tone="muted",
        )
        layout.addWidget(self.header)

        # Top Orb + Activation Controls
        hero = GlassCard()
        hero_row = QHBoxLayout()
        self.orb = VoiceOrbWidget()
        hero_row.addWidget(self.orb)

        ctrl_col = QVBoxLayout()
        ctrl_col.setSpacing(8)
        self.state_lbl = QLabel("Voice Engine State: Idle (Microphone Off)")
        self.state_lbl.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.privacy_lbl = QLabel(
            "Privacy Guarantee: Microphone opens only when you explicitly arm a listening mode."
        )
        self.privacy_lbl.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 12px;")

        btn_row = QHBoxLayout()
        self.wake_btn = QPushButton('Arm "Hey Aspirant"')
        self.wake_btn.setProperty("variant", "primary")
        self.wake_btn.clicked.connect(lambda: self._start_mode("wake_word"))

        self.ptt_btn = QPushButton("Push-to-Talk")
        self.ptt_btn.setProperty("variant", "ghost")
        self.ptt_btn.clicked.connect(lambda: self._start_mode("push_to_talk"))

        self.handsfree_btn = QPushButton("Hands-Free")
        self.handsfree_btn.setProperty("variant", "ghost")
        self.handsfree_btn.clicked.connect(lambda: self._start_mode("hands_free"))

        self.live_btn = QPushButton("Gemini 3.8 Live")
        self.live_btn.setProperty("variant", "primary")
        self.live_btn.clicked.connect(lambda: self._start_mode("gemini_live"))

        self.interrupt_btn = QPushButton("Interrupt (Barge-In)")
        self.interrupt_btn.setProperty("variant", "ghost")
        self.interrupt_btn.clicked.connect(self._interrupt)

        self.stop_btn = QPushButton("Stop Mic")
        self.stop_btn.setProperty("variant", "danger")
        self.stop_btn.clicked.connect(self._stop_mode)

        for b in (self.wake_btn, self.ptt_btn, self.handsfree_btn, self.live_btn, self.interrupt_btn, self.stop_btn):
            btn_row.addWidget(b)

        ctrl_col.addWidget(self.state_lbl)
        ctrl_col.addWidget(self.privacy_lbl)
        ctrl_col.addLayout(btn_row)
        hero_row.addLayout(ctrl_col, 1)
        hero.body_layout.addLayout(hero_row)
        layout.addWidget(hero)

        # Female Voice Tuning & Provider Settings
        tuning = GlassCard()
        t_title = QLabel("Female Voice & Speech Settings")
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

        self._thread = QThread(self)
        self._worker = _VoiceActionWorker(self.api_client)
        self._worker.moveToThread(self._thread)
        self.run_action.connect(self._worker.run)
        self._worker.finished.connect(self._on_action_done)
        self._worker.failed.connect(self._on_action_failed)
        self._thread.start()

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
        self.voice_feedback_pill.set_tone("ok", f"DONE ({res.get('provider', res.get('tts', {}).get('provider', 'ok'))})")
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
            "idle": ("Idle (Microphone Off)", "muted"),
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

    def shutdown(self) -> None:
        self._thread.quit()
        self._thread.wait(1200)
