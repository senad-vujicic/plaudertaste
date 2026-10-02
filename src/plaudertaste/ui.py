"""Kleine gemeinsame Bausteine für die Seiten des Hauptfensters.

Das Aussehen kommt aus theme.py – hier werden nur die passenden objectNames gesetzt.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QLayout, QVBoxLayout, QWidget

from plaudertaste import theme


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    return label


def page_title(text: str) -> QLabel:
    return _label(text, "pageTitle")


def card_title(text: str) -> QLabel:
    return _label(text, "cardTitle")


def muted_label(text: str = "") -> QLabel:
    """Erklärender Text in gedämpfter Farbe."""
    label = _label(text, "muted")
    label.setWordWrap(True)
    return label


def hint_label() -> QLabel:
    """Hinweis in Orange (kein Fehler) – unsichtbar, solange er leer ist."""
    label = _label("", "hint")
    label.setWordWrap(True)
    label.setVisible(False)
    return label


def set_hint(label: QLabel, text: str) -> None:
    label.setText(text)
    label.setVisible(bool(text))


def card(*items: QWidget | QLayout, spacing: int = 10) -> QFrame:
    """Abgerundete Karte, die Widgets und Layouts untereinander anordnet."""
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(spacing)
    for item in items:
        if isinstance(item, QLayout):
            layout.addLayout(item)
        else:
            layout.addWidget(item)
    return frame


class ToggleSwitch(QCheckBox):
    """Schalter im Stil moderner Apps – verhält sich wie eine normale QCheckBox."""

    _TRACK_W, _TRACK_H, _GAP = 38, 20, 12

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        metrics = self.fontMetrics()
        width = self._TRACK_W + self._GAP + metrics.horizontalAdvance(self.text())
        return QSize(width, max(self._TRACK_H + 6, metrics.height() + 6))

    def hitButton(self, pos: QPoint) -> bool:
        return self.rect().contains(pos)  # auch ein Klick auf den Text schaltet

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = (self.height() - self._TRACK_H) / 2
        track = QRectF(0, top, self._TRACK_W, self._TRACK_H)

        track_color = QColor(theme.ACCENT if self.isChecked() else "#3a3a46")
        if not self.isEnabled():
            track_color.setAlpha(110)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, self._TRACK_H / 2, self._TRACK_H / 2)

        knob = self._TRACK_H - 6
        knob_x = track.right() - knob - 3 if self.isChecked() else track.left() + 3
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QRectF(knob_x, top + 3, knob, knob))

        painter.setPen(self.palette().windowText().color())
        text_area = QRectF(self._TRACK_W + self._GAP, 0, self.width(), self.height())
        painter.drawText(
            text_area, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text()
        )
        painter.end()


def format_duration(seconds: float) -> str:
    """45 s, 3 min, 1 h 05 min."""
    seconds = round(seconds)
    if seconds < 60:
        return f"{seconds} s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d} min"


def count_text(count: int, singular: str, plural: str) -> str:
    """1 Wort, 2 Wörter – mit Tausenderpunkt (1.234 Wörter)."""
    return f"{format_number(count)} {singular if count == 1 else plural}"


def format_number(count: int) -> str:
    """Deutscher Tausenderpunkt: 1234 -> 1.234."""
    return f"{count:,}".replace(",", ".")
