"""Interactive 3D-projected animated AI Robot widget for PySide6 desktop views."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QApplication, QWidget

from aspirant.robot.animation_controller import ROBOT_STATE_PROFILES, compute_animation_frame


class Robot3DWidget(QWidget):
    """Animated futuristic dark-glass AI Robot visualizing all 8 operational states."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(210, 210)
        self._state = "IDLE"
        self._phase = 0.0
        self._speech_amplitude = 0.0
        self._status_text = "Standing by ('Hey Baby')"
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    def shutdown(self) -> None:
        """Stop animation timer cleanly before Qt teardown."""
        if self._timer.isActive():
            self._timer.stop()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.shutdown()
        super().closeEvent(event)

    @property
    def current_state(self) -> str:
        return self._state

    def set_robot_state(
        self, state: str, *, status_text: str | None = None, speech_amplitude: float = 0.0
    ) -> None:
        upper = state.strip().upper()
        if upper in ROBOT_STATE_PROFILES:
            self._state = upper
        self._speech_amplitude = max(0.0, min(1.0, float(speech_amplitude)))
        if status_text:
            self._status_text = status_text
        else:
            self._status_text = ROBOT_STATE_PROFILES.get(
                self._state, ROBOT_STATE_PROFILES["IDLE"]
            ).status_badge
        self.update()

    def _tick(self) -> None:
        prof = ROBOT_STATE_PROFILES.get(self._state, ROBOT_STATE_PROFILES["IDLE"])
        self._phase = (self._phase + 0.05 * max(0.5, prof.ring_speed)) % 62.8318
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        frame = compute_animation_frame(
            self._state, self._phase, speech_amplitude=self._speech_amplitude
        )
        accent = QColor(frame["accent_hex"])
        glow = QColor(frame["glow_hex"])

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = float(self.width()), float(self.height())
        cx = w / 2.0
        cy = h / 2.0 - 10.0 + frame["breathing_y"] * 75.0
        tilt_x = frame["head_yaw"] * 18.0

        # Background ambient aura
        aura = QRadialGradient(cx, cy, min(w, h) * 0.46)
        a_inner = QColor(accent)
        a_inner.setAlpha(75)
        a_mid = QColor(glow)
        a_mid.setAlpha(28)
        a_out = QColor(glow)
        a_out.setAlpha(0)
        aura.setColorAt(0.0, a_inner)
        aura.setColorAt(0.6, a_mid)
        aura.setColorAt(1.0, a_out)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(aura)
        painter.drawEllipse(int(cx - w * 0.44), int(cy - h * 0.42), int(w * 0.88), int(h * 0.84))

        # Orbital holographic ring
        ring_pen = QPen(accent, 2.0)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        ring_rx = min(w * 0.4, 86.0)
        ring_ry = 22.0 + math.sin(self._phase) * 4.0
        painter.drawEllipse(int(cx - ring_rx), int(cy + 14.0 - ring_ry), int(ring_rx * 2), int(ring_ry * 2))

        # Listening / Speaking sound-wave pulse ring
        if frame["wave_bars_active"]:
            wave_r = min(w * 0.42, 92.0) + math.sin(self._phase * 2.2) * 8.0
            wave_c = QColor(accent)
            wave_c.setAlpha(135)
            painter.setPen(QPen(wave_c, 1.8))
            painter.drawEllipse(int(cx - wave_r), int(cy - wave_r * 0.72), int(wave_r * 2), int(wave_r * 1.44))

        # Robot sculpted head shell
        head_x = cx - 44.0 + tilt_x
        head_y = cy - 58.0
        shell_grad = QLinearGradient(head_x, head_y, head_x + 88.0, head_y + 66.0)
        shell_grad.setColorAt(0.0, QColor("#1E293B"))
        shell_grad.setColorAt(1.0, QColor("#090D1A"))
        painter.setPen(QPen(accent, 2.2))
        painter.setBrush(shell_grad)
        painter.drawRoundedRect(int(head_x), int(head_y), 88, 66, 20, 20)

        # Antenna halo tip
        painter.setPen(QPen(QColor("#64748B"), 2.0))
        painter.drawLine(int(cx + tilt_x), int(head_y), int(cx + tilt_x), int(head_y - 16))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(int(cx + tilt_x - 5), int(head_y - 23), 10, 10)

        # Glass visor
        painter.setBrush(QColor("#040814"))
        painter.setPen(QPen(glow, 1.0))
        painter.drawRoundedRect(int(head_x + 11), int(head_y + 13), 66, 38, 10, 10)

        # Expressive LED eyes
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        eye_h = max(2, int(13 * frame["blink_open"]))
        eye_y = int(head_y + 22 + (13 - eye_h) / 2)
        if frame["eye_mode"] == "code_visor":
            painter.drawRoundedRect(int(head_x + 20), int(head_y + 26), 18, 4, 2, 2)
            painter.drawRoundedRect(int(head_x + 50), int(head_y + 26), 18, 4, 2, 2)
        else:
            painter.drawEllipse(int(head_x + 23), eye_y, 11, eye_h)
            painter.drawEllipse(int(head_x + 54), eye_y, 11, eye_h)

        # Equalizer mouth bars synchronized with speech amplitude
        mouth_amp = float(frame["mouth_open"])
        for idx in range(5):
            harm = 0.65 + 0.35 * math.sin(self._phase * 2.8 + idx * 1.1)
            bar_h = max(3, int((3.0 + mouth_amp * 10.0) * harm))
            bx = int(head_x + 27 + idx * 7)
            by = int(head_y + 44 - bar_h / 2)
            painter.drawRoundedRect(bx, by, 4, bar_h, 2, 2)

        # Torso + Chest reactor core
        torso_x = cx - 32.0
        torso_y = head_y + 72.0
        painter.setPen(QPen(glow, 1.8))
        painter.setBrush(QColor("#0F172A"))
        painter.drawRoundedRect(int(torso_x), int(torso_y), 64, 48, 14, 14)

        core_r = 9.0 + math.sin(self._phase * 1.8) * 1.8
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(int(cx - core_r), int(torso_y + 24 - core_r), int(core_r * 2), int(core_r * 2))

        # Status badge caption
        painter.setPen(accent)
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            0,
            int(h - 24),
            int(w),
            20,
            Qt.AlignmentFlag.AlignCenter,
            f"🤖 {self._state} • {self._status_text[:34]}",
        )
        painter.end()
