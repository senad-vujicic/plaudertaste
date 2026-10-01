"""Overlay unten am Bildschirm: Pegel und Zeit während der Aufnahme, Punkte beim Verarbeiten.

Wichtig: Das Fenster darf nie den Fokus bekommen – sonst landete der eingefügte Text
im Overlay statt im eigentlichen Programm. Mausklicks gehen durch es hindurch.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from plaudertaste.app import Status

WIDTH, HEIGHT = 230, 44
BOTTOM_MARGIN = 24
BAR_COUNT = 16
FRAME_MS = 33  # ~30 Bilder pro Sekunde

BACKGROUND = QColor(28, 28, 30, 235)
BORDER = QColor(255, 255, 255, 40)
RED = QColor("#e53935")
YELLOW = QColor("#f9a825")
BAR = QColor(235, 235, 235)
TEXT = QColor(220, 220, 220)

SILENCE_DB = -60.0  # leiser als das zählt als Stille
LOUD_DB = -12.0  # ab hier volle Balkenhöhe


def level_to_height(rms: float) -> float:
    """Wandelt die Lautstärke (RMS) in eine Balkenhöhe 0–1 – logarithmisch wie das Gehör."""
    if rms <= 0:
        return 0.0
    db = 20 * math.log10(rms)
    return min(1.0, max(0.0, (db - SILENCE_DB) / (LOUD_DB - SILENCE_DB)))


def format_elapsed(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"


class Overlay(QWidget):
    def __init__(self, level_source: Callable[[], float]) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # kein Eintrag in der Taskleiste
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(WIDTH, HEIGHT)

        self._level_source = level_source
        self._levels: deque[float] = deque([0.0] * BAR_COUNT, maxlen=BAR_COUNT)
        self._status: Status | None = None
        self._started = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)

    @property
    def status(self) -> Status | None:
        return self._status

    def set_status(self, status: Status) -> None:
        if status is Status.RECORDING:
            if self._status is not Status.RECORDING:
                self._levels.extend([0.0] * BAR_COUNT)
                self._started = time.monotonic()
                self._move_to_current_screen()
        elif status is not Status.PROCESSING:
            self._status = None
            self._timer.stop()
            self.hide()
            return
        self._status = status
        self.show()
        self._timer.start()

    def _move_to_current_screen(self) -> None:
        """Unten mittig auf dem Bildschirm, auf dem gerade der Mauszeiger ist."""
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()  # ohne Taskleiste
        self.move(area.center().x() - WIDTH // 2, area.bottom() - HEIGHT - BOTTOM_MARGIN)

    def _tick(self) -> None:
        if self._status is Status.RECORDING:
            self._levels.append(level_to_height(self._level_source()))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pill = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(BORDER, 1))
        painter.setBrush(BACKGROUND)
        painter.drawRoundedRect(pill, HEIGHT / 2, HEIGHT / 2)

        if self._status is Status.RECORDING:
            self._paint_recording(painter)
        elif self._status is Status.PROCESSING:
            self._paint_processing(painter)
        painter.end()

    def _paint_recording(self, painter: QPainter) -> None:
        middle = HEIGHT / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(RED)
        painter.drawEllipse(QRectF(16, middle - 6, 12, 12))

        painter.setBrush(BAR)
        bar_width, gap, left = 4, 3, 42
        max_height = HEIGHT - 18
        for i, level in enumerate(self._levels):
            height = 3 + level * (max_height - 3)
            x = left + i * (bar_width + gap)
            painter.drawRoundedRect(QRectF(x, middle - height / 2, bar_width, height), 2, 2)

        painter.setPen(TEXT)
        painter.setFont(QFont("Segoe UI", 10))
        text_area = QRectF(WIDTH - 62, 0, 46, HEIGHT)
        painter.drawText(
            text_area,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            format_elapsed(time.monotonic() - self._started),
        )

    def _paint_processing(self, painter: QPainter) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        phase = time.monotonic() * 6
        for i in range(3):
            pulse = 0.5 + 0.5 * math.sin(phase - i * 0.9)  # wandernde Welle
            color = QColor(YELLOW)
            color.setAlphaF(0.35 + 0.65 * pulse)
            painter.setBrush(color)
            radius = 4 + 1.5 * pulse
            center_x = WIDTH / 2 + (i - 1) * 18
            painter.drawEllipse(QRectF(center_x - radius, HEIGHT / 2 - radius, 2 * radius, 2 * radius))
