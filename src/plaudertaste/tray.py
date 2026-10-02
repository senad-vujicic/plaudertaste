"""Tray-Icon: Taste, deren Farbe den Status zeigt, plus Rechtsklick-Menü."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from plaudertaste.app import Status
from plaudertaste.icons import make_status_icon


def open_file(path: Path) -> None:
    """Öffnet eine Datei im zugeordneten Programm, sonst im Windows-Editor."""
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
        subprocess.Popen(["notepad.exe", str(path)])


class Tray(QSystemTrayIcon):
    quit_requested = Signal()
    open_requested = Signal()
    settings_requested = Signal()
    sound_toggled = Signal(bool)
    overlay_toggled = Signal(bool)

    def __init__(
        self,
        hotkey_label: str,
        sound_enabled: bool,
        overlay_enabled: bool,
        config_file: Path,
        log_file: Path,
    ) -> None:
        super().__init__()
        self._hotkey_label = hotkey_label
        self._status = Status.LOADING
        self._icons = {status: make_status_icon(status) for status in Status}

        self._menu = QMenu()
        self._status_action = QAction()
        self._status_action.setEnabled(False)
        self._menu.addAction(self._status_action)
        self._menu.addSeparator()
        open_action = self._menu.addAction("Plaudertaste öffnen", self.open_requested.emit)
        self._menu.setDefaultAction(open_action)  # fett dargestellt, wie bei Windows üblich
        self._menu.addAction("Einstellungen …", self.settings_requested.emit)
        self._menu.addSeparator()
        self.sound_action = QAction("Ton bei Aufnahme", checkable=True, checked=sound_enabled)
        self.sound_action.toggled.connect(self.sound_toggled)
        self._menu.addAction(self.sound_action)
        self.overlay_action = QAction("Overlay anzeigen", checkable=True, checked=overlay_enabled)
        self.overlay_action.toggled.connect(self.overlay_toggled)
        self._menu.addAction(self.overlay_action)
        self._menu.addSeparator()
        self._menu.addAction("Konfigurationsdatei öffnen", lambda: open_file(config_file))
        self._menu.addAction("Logdatei öffnen", lambda: open_file(log_file))
        self._menu.addSeparator()
        self._menu.addAction("Beenden", self.quit_requested.emit)
        self.setContextMenu(self._menu)
        self.activated.connect(self._on_activated)

        self.set_status(Status.LOADING)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason is QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_requested.emit()

    def set_hotkey_label(self, label: str) -> None:
        self._hotkey_label = label
        self.set_status(self._status)

    def set_toggles(self, sound: bool, overlay: bool) -> None:
        """Häkchen setzen, ohne die toggled-Signale auszulösen (Änderung kam von außen)."""
        with QSignalBlocker(self.sound_action), QSignalBlocker(self.overlay_action):
            self.sound_action.setChecked(sound)
            self.overlay_action.setChecked(overlay)

    def set_download_progress(self, model: str, percent: int) -> None:
        text = f"Lade Sprachmodell „{model}“: {percent} %"
        self._status_action.setText(text)
        self.setToolTip(f"Plaudertaste – {text}")

    def set_status(self, status: Status) -> None:
        self._status = status
        self.setIcon(self._icons[status])
        text = status.value
        if status is Status.READY:
            text = f"Bereit – {self._hotkey_label} halten zum Sprechen"
        self._status_action.setText(text)
        self.setToolTip(f"Plaudertaste – {text}")
