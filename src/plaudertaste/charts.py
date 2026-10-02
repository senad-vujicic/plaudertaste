"""Flächendiagramm für die Statistik: weiche Kurve mit Lavendel-Verlauf darunter."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from plaudertaste import theme
from plaudertaste.ui import format_number

GRID_LINES = 4
LEFT, RIGHT, TOP, BOTTOM = 44, 8, 8, 26  # Platz für Achsenbeschriftungen


def nice_ceiling(value: float) -> int:
    """Runde Obergrenze für die y-Achse: 1, 2, 5, 10, 20, 50 … – mindestens 10."""
    if value <= 10:
        return 10
    magnitude = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 5, 10):
        if value <= step * magnitude:
            return step * magnitude
    return 10 * magnitude  # nicht erreichbar, beruhigt aber die Typprüfung


def smooth_path(points: list[QPointF]) -> QPainterPath:
    """Weiche Linie durch alle Punkte (Catmull-Rom als Bézierkurven).

    Die Kontrollpunkte werden auf den Wertebereich der Nachbarn begrenzt – so schießt die
    Kurve nie unter die Nulllinie oder über einen Spitzenwert hinaus.
    """
    path = QPainterPath(points[0])
    for i in range(len(points) - 1):
        p0 = points[max(i - 1, 0)]
        p1, p2 = points[i], points[i + 1]
        p3 = points[min(i + 2, len(points) - 1)]
        low, high = min(p1.y(), p2.y()), max(p1.y(), p2.y())
        c1 = QPointF(p1.x() + (p2.x() - p0.x()) / 6, p1.y() + (p2.y() - p0.y()) / 6)
        c2 = QPointF(p2.x() - (p3.x() - p1.x()) / 6, p2.y() - (p3.y() - p1.y()) / 6)
        c1.setY(min(max(c1.y(), low), high))
        c2.setY(min(max(c2.y(), low), high))
        path.cubicTo(c1, c2, p2)
    return path


class AreaChart(QWidget):
    def __init__(self, empty_text: str) -> None:
        super().__init__()
        self._labels: list[str] = []
        self._values: list[int] = []
        self._empty_text = empty_text
        self.setMinimumHeight(200)

    def set_data(self, labels: list[str], values: list[int]) -> None:
        self._labels, self._values = labels, values
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = QRectF(self.rect()).adjusted(LEFT, TOP, -RIGHT, -BOTTOM)
        top_value = nice_ceiling(max(self._values, default=0))
        self._paint_grid(painter, plot, top_value)
        if len(self._values) >= 2 and any(self._values):
            self._paint_curve(painter, plot, top_value)
        else:
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, self._empty_text)
        painter.end()

    def _paint_grid(self, painter: QPainter, plot: QRectF, top_value: int) -> None:
        grid = QColor(theme.BORDER)
        for i in range(GRID_LINES + 1):
            y = plot.bottom() - plot.height() * i / GRID_LINES
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(
                QRectF(0, y - 10, LEFT - 10, 20),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                format_number(top_value * i // GRID_LINES),
            )
        if len(self._labels) < 2:
            return
        step = plot.width() / (len(self._labels) - 1)
        for i, label in enumerate(self._labels):
            if i % 2 != (len(self._labels) - 1) % 2:  # jede zweite, der heutige Tag immer
                continue
            x = plot.left() + i * step
            box = QRectF(x - 30, plot.bottom() + 6, 60, BOTTOM - 6)
            box.moveRight(min(box.right(), self.width()))  # am Rand nicht abschneiden
            painter.drawText(box, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)

    def _paint_curve(self, painter: QPainter, plot: QRectF, top_value: int) -> None:
        step = plot.width() / (len(self._values) - 1)
        points = [
            QPointF(plot.left() + i * step, plot.bottom() - plot.height() * value / top_value)
            for i, value in enumerate(self._values)
        ]
        line = smooth_path(points)

        area = QPainterPath(line)
        area.lineTo(plot.right(), plot.bottom())
        area.lineTo(plot.left(), plot.bottom())
        area.closeSubpath()
        gradient = QLinearGradient(0, plot.top(), 0, plot.bottom())
        fill = QColor(theme.LAVENDER)
        fill.setAlpha(150)
        gradient.setColorAt(0, fill)
        fill.setAlpha(0)
        gradient.setColorAt(1, fill)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(area)

        painter.setPen(QPen(QColor(theme.LAVENDER), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(line)

        today = points[-1]  # heutiger Wert als Punkt hervorheben
        painter.setPen(QPen(QColor(theme.SURFACE), 2))
        painter.setBrush(QColor(theme.ACCENT))
        painter.drawEllipse(today, 5, 5)
