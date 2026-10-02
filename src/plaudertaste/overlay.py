"""Overlay unten am Bildschirm: Pegel und Zeit während der Aufnahme, Punkte beim Verarbeiten,
rote Kurzmeldung bei Problemen.

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

from plaudertaste import theme
from plaudertaste.app import Status

WIDTH, HEIGHT = 230, 44
BOTTOM_MARGIN = 24
BAR_COUNT = 16
FRAME_MS = 33  # ~30 Bilder pro Sekunde
MESSAGE_MS = 4000  # so lange bleibt eine Meldung stehen
MAX_MESSAGE_WIDTH = 640
HANDS_FREE_EXTRA = 84  # Platz für den Hinweis "Freihand"

BACKGROUND = QColor(28, 28, 30, 235)
BORDER = QColor(255, 255, 255, 40)
RED = QColor(theme.STATUS_RED)
YELLOW = QColor(theme.STATUS_YELLOW)
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
        self._message: str | None = None
        self._hands_free = False
        self._message_timer = QTimer(self, singleShot=True, interval=MESSAGE_MS)
        self._message_timer.timeout.connect(self._hide_message)
        # Schriften einmal anlegen statt bei jedem der ~30 Bilder pro Sekunde
        self._font = QFont("Segoe UI", 10)
        self._bold_font = QFont("Segoe UI", 10)
        self._bold_font.setBold(True)

    @property
    def status(self) -> Status | None:
        return self._status

    @property
    def message(self) -> str | None:
        return self._message

    def set_status(self, status: Status) -> None:
        if status is Status.RECORDING:
            if self._status is not Status.RECORDING:
                self._levels.extend([0.0] * BAR_COUNT)
                self._started = time.monotonic()
                self._end_message()
                self._move_to_current_screen()
        elif status is not Status.PROCESSING:
            self._status = None
            self._timer.stop()
            if self._message is None:  # eine gerade gezeigte Meldung bleibt stehen
                self.hide()
            return
        self._end_message()
        self._status = status
        self.show()
        self._timer.start()

    def set_hands_free(self, hands_free: bool) -> None:
        """Zeigt "Freihand" an – dann muss man zum Beenden einmal tippen statt loslassen."""
        if hands_free == self._hands_free:
            return
        self._hands_free = hands_free
        if self._message is None:
            self.setFixedSize(WIDTH + HANDS_FREE_EXTRA if hands_free else WIDTH, HEIGHT)
            if self.isVisible():
                self._move_to_current_screen()
        self.update()

    def show_message(self, text: str) -> None:
        """Rote Kurzmeldung, verschwindet nach ein paar Sekunden von selbst."""
        self._status = None
        self._timer.stop()
        self._message = text
        width = self.fontMetrics().horizontalAdvance(text) + 76
        self.setFixedSize(max(WIDTH, min(width, MAX_MESSAGE_WIDTH)), HEIGHT)
        self._move_to_current_screen()
        self.show()
        self.update()
        self._message_timer.start()

    def _end_message(self) -> None:
        if self._message is not None:
            self._message = None
            self._message_timer.stop()
            self.setFixedSize(WIDTH, HEIGHT)

    def _hide_message(self) -> None:
        self._end_message()
        if self._status is None:
            self.hide()

    def _move_to_current_screen(self) -> None:
        """Unten mittig auf dem Bildschirm, auf dem gerade der Mauszeiger ist."""
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()  # ohne Taskleiste
        self.move(area.center().x() - self.width() // 2, area.bottom() - HEIGHT - BOTTOM_MARGIN)

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

        if self._message is not None:
            self._paint_message(painter, self._message)
        elif self._status is Status.RECORDING:
            self._paint_recording(painter)
        elif self._status is Status.PROCESSING:
            self._paint_processing(painter)
        painter.end()

    def _paint_message(self, painter: QPainter, text: str) -> None:
        middle = HEIGHT / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(RED)
        painter.drawEllipse(QRectF(14, middle - 9, 18, 18))
        painter.setPen(QColor("white"))
        painter.setFont(self._bold_font)
        painter.drawText(QRectF(14, middle - 9, 18, 18), Qt.AlignmentFlag.AlignCenter, "!")
        painter.setPen(TEXT)
        painter.setFont(self._font)
        text_area = QRectF(42, 0, self.width() - 58, HEIGHT)
        elided = self.fontMetrics().elidedText(
            text, Qt.TextElideMode.ElideRight, int(text_area.width())
        )
        painter.drawText(
            text_area, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided
        )

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
        painter.setFont(self._font)
        if self._hands_free:
            painter.setPen(RED)
            painter.drawText(
                QRectF(self.width() - 140, 0, 76, HEIGHT),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "Freihand",
            )
            painter.setPen(TEXT)
        text_area = QRectF(self.width() - 62, 0, 46, HEIGHT)
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
            center_x = self.width() / 2 + (i - 1) * 18
            painter.drawEllipse(
                QRectF(center_x - radius, HEIGHT / 2 - radius, 2 * radius, 2 * radius)
            )
