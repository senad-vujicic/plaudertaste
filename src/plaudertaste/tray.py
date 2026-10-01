"""Tray-Icon: Sprechblase, deren Farbe den Status zeigt, plus Rechtsklick-Menü."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from plaudertaste.app import Status

STATUS_COLORS: dict[Status, str] = {
    Status.LOADING: "#8e959e",  # grau, nur Umriss
    Status.READY: "#8e959e",  # grau
    Status.RECORDING: "#e53935",  # rot
    Status.PROCESSING: "#f9a825",  # gelb
}
_ICON_SIZES = (16, 24, 32, 48, 64)


def _draw_bubble(status: Status, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    s = size / 64  # alle Maße beziehen sich auf eine 64×64-Vorlage

    bubble = QPainterPath()
    bubble.addRoundedRect(QRectF(4 * s, 6 * s, 56 * s, 40 * s), 14 * s, 14 * s)
    tail = QPainterPath()
    tail.moveTo(16 * s, 40 * s)
    tail.lineTo(10 * s, 58 * s)
    tail.lineTo(32 * s, 44 * s)
    tail.closeSubpath()
    bubble = bubble.united(tail)

    color = QColor(STATUS_COLORS[status])
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if status is Status.LOADING:
        painter.setPen(QPen(color, 5 * s))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        dot_color = color
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        dot_color = QColor("white")
    painter.drawPath(bubble)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(dot_color)
    for x in (20, 32, 44):  # drei Punkte = "es wird geplaudert"
        painter.drawEllipse(QPointF(x * s, 26 * s), 4.5 * s, 4.5 * s)
    painter.end()
    return pixmap


def make_icon(status: Status) -> QIcon:
    icon = QIcon()
    for size in _ICON_SIZES:
        icon.addPixmap(_draw_bubble(status, size))
    return icon


def open_file(path: Path) -> None:
    """Öffnet eine Datei im zugeordneten Programm, sonst im Windows-Editor."""
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
        subprocess.Popen(["notepad.exe", str(path)])


class Tray(QSystemTrayIcon):
    quit_requested = Signal()

    def __init__(self, hotkey_label: str, config_file: Path, log_file: Path) -> None:
        super().__init__()
        self._hotkey_label = hotkey_label
        self._icons = {status: make_icon(status) for status in Status}

        self._menu = QMenu()
        self._status_action = QAction()
        self._status_action.setEnabled(False)
        self._menu.addAction(self._status_action)
        self._menu.addSeparator()
        self._menu.addAction("Konfigurationsdatei öffnen", lambda: open_file(config_file))
        self._menu.addAction("Logdatei öffnen", lambda: open_file(log_file))
        self._menu.addSeparator()
        self._menu.addAction("Beenden", self.quit_requested.emit)
        self.setContextMenu(self._menu)

        self.set_status(Status.LOADING)

    def set_status(self, status: Status) -> None:
        self.setIcon(self._icons[status])
        text = status.value
        if status is Status.READY:
            text = f"Bereit – {self._hotkey_label} halten zum Sprechen"
        self._status_action.setText(text)
        self.setToolTip(f"Plaudertaste – {text}")
