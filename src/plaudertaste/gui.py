"""Qt-Oberfläche: verbindet Tray-Icon, Modell-Laden und Diktat-Ablauf.

Qt-Regel: Fenster und Icon dürfen nur im Haupt-Thread verändert werden. Tastatur-Listener,
Modell-Lader und Worker laufen in eigenen Threads und melden sich deshalb über Qt-Signale.
Ein Signal aus einem anderen Thread wird automatisch in den Haupt-Thread weitergereicht.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
from pathlib import Path

from pynput import keyboard
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from plaudertaste import paths
from plaudertaste.app import App
from plaudertaste.config import Config, ConfigError, load_config
from plaudertaste.hotkey import PushToTalk, describe_hotkey, parse_hotkey, start_listener
from plaudertaste.recorder import Recorder
from plaudertaste.single_instance import acquire_single_instance_lock
from plaudertaste.transcriber import Transcriber
from plaudertaste.tray import Tray

log = logging.getLogger(__name__)

TITLE = "Plaudertaste"


class Controller(QObject):
    status_changed = Signal(object)  # Status – aus App-Threads
    model_loaded = Signal(object)  # Transcriber – aus dem Lade-Thread
    model_failed = Signal(str)

    def __init__(self, config: Config, combo: frozenset[str], log_file: Path) -> None:
        super().__init__()
        self._config = config
        self._combo = combo
        self._log_file = log_file
        self._app: App | None = None
        self._listener: keyboard.Listener | None = None

        self.tray = Tray(describe_hotkey(config.hotkey), paths.config_file(), log_file)
        self.tray.quit_requested.connect(self.shutdown)
        self.status_changed.connect(self.tray.set_status)
        self.model_loaded.connect(self._on_model_loaded)
        self.model_failed.connect(self._on_model_failed)

    def start(self) -> None:
        self.tray.show()
        # Laden im Hintergrund, damit das Icon sofort erscheint.
        threading.Thread(target=self._load_model, name="model-loader", daemon=True).start()

    def _load_model(self) -> None:
        try:
            transcriber = Transcriber(self._config.model, self._config.device, self._config.language)
        except Exception as exc:
            log.exception("Modell konnte nicht geladen werden")
            self.model_failed.emit(str(exc))
            return
        self.model_loaded.emit(transcriber)

    def _on_model_loaded(self, transcriber: Transcriber) -> None:
        choice = transcriber.choice
        log.info("Modell '%s' bereit (%s).", choice.name, choice.device.upper())
        self._app = App(transcriber, Recorder(), on_status=self.status_changed.emit)
        self._app.start()
        push_to_talk = PushToTalk(
            self._combo, self._app.on_start, self._app.on_stop, self._app.on_cancel
        )
        self._listener = start_listener(push_to_talk)
        log.info("Bereit! Halte [%s] gedrückt und sprich.", describe_hotkey(self._config.hotkey))

    def _on_model_failed(self, message: str) -> None:
        QMessageBox.critical(
            None,
            TITLE,
            "Das Sprachmodell konnte nicht geladen werden:\n\n"
            f"{message}\n\n"
            "Beim ersten Start wird eine Internetverbindung für den Download benötigt.\n"
            f"Details in der Logdatei:\n{self._log_file}",
        )
        self.shutdown()

    def shutdown(self) -> None:
        log.info("Plaudertaste wird beendet.")
        if self._listener is not None:
            self._listener.stop()
        if self._app is not None:
            self._app.stop()
        self.tray.hide()
        QApplication.quit()


def run(log_file: Path) -> int:
    qapp = QApplication(sys.argv)
    qapp.setApplicationName(TITLE)
    qapp.setQuitOnLastWindowClosed(False)  # Tray-App: läuft ohne offenes Fenster weiter

    lock = acquire_single_instance_lock(paths.lock_file())
    if lock is None:
        log.error("Plaudertaste läuft bereits – zweiter Start abgebrochen.")
        QMessageBox.information(
            None, TITLE, "Plaudertaste läuft bereits.\n\n"
            "Du findest es unten rechts im Infobereich der Taskleiste."
        )
        return 1

    if not QSystemTrayIcon.isSystemTrayAvailable():
        log.error("Kein Infobereich (System-Tray) verfügbar.")
        QMessageBox.critical(None, TITLE, "Der Infobereich der Taskleiste ist nicht verfügbar.")
        return 1

    config_path = paths.config_file()
    try:
        config = load_config(config_path)
        combo = parse_hotkey(config.hotkey)
    except (ConfigError, ValueError) as exc:
        log.error("Konfiguration ungültig: %s (Datei: %s)", exc, config_path)
        QMessageBox.critical(
            None, TITLE, f"Die Konfiguration ist ungültig:\n\n{exc}\n\nDatei:\n{config_path}"
        )
        return 1
    log.info("Konfiguration: %s", config_path)

    controller = Controller(config, combo, log_file)
    controller.start()

    # Strg+C in der Konsole: Qt blockiert Python-Signale, solange die Ereignisschleife
    # läuft. Ein kurzer Timer gibt Python regelmäßig die Gelegenheit, sie zu verarbeiten.
    signal.signal(signal.SIGINT, lambda *_: controller.shutdown())
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start(200)

    exit_code = qapp.exec()
    lock.unlock()
    return exit_code
