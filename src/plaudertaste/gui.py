"""Qt-Oberfläche: verbindet Tray-Icon, Einstellungen, Modell-Laden und Diktat-Ablauf.

Qt-Regel: Fenster und Icon dürfen nur im Haupt-Thread verändert werden. Tastatur-Listener,
Modell-Lader und Worker laufen in eigenen Threads und melden sich deshalb über Qt-Signale.
Ein Signal aus einem anderen Thread wird automatisch in den Haupt-Thread weitergereicht.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
from dataclasses import replace
from pathlib import Path

from pynput import keyboard
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QSystemTrayIcon

from plaudertaste import autostart, paths
from plaudertaste.app import App, Status
from plaudertaste.catalog import AUTO, MODELS, is_model_downloaded
from plaudertaste.config import Config, ConfigError, load_config, save_config
from plaudertaste.devices import list_microphones
from plaudertaste.hotkey import (
    HotkeyCapture,
    PushToTalk,
    describe_hotkey,
    parse_hotkey,
    start_listener,
)
from plaudertaste.overlay import Overlay
from plaudertaste.recorder import Recorder
from plaudertaste.settings_dialog import Settings, SettingsDialog
from plaudertaste.single_instance import acquire_single_instance_lock
from plaudertaste.sounds import TonePlayer, tone_for_transition
from plaudertaste.transcriber import Transcriber
from plaudertaste.tray import Tray

log = logging.getLogger(__name__)

TITLE = "Plaudertaste"


def whisper_language(setting: str) -> str | None:
    """Config-Wert -> Whisper-Parameter ("auto" heißt: Whisper erkennt selbst)."""
    return None if setting == AUTO else setting


class Controller(QObject):
    status_changed = Signal(object)  # Status – aus App-Threads
    model_loaded = Signal(object)  # Transcriber – aus dem Lade-Thread
    model_failed = Signal(str)
    hotkey_captured = Signal(str)  # aus dem Tastatur-Thread

    def __init__(self, config: Config, log_file: Path) -> None:
        super().__init__()
        self._config = config
        self._log_file = log_file
        self._app: App | None = None
        self._listener: keyboard.Listener | None = None
        # Tastendrücke gehen an genau einen Empfänger: Push-to-Talk oder Hotkey-Aufnahme.
        self._key_target: PushToTalk | HotkeyCapture | None = None
        self._push_to_talk: PushToTalk | None = None
        self._status = Status.LOADING
        self._recorder = Recorder(config.microphone)
        self._tones = TonePlayer(config.sound)
        self._overlay = Overlay(level_source=lambda: self._recorder.level)
        self._settings_dialog: SettingsDialog | None = None
        self._config_before_model_change: Config | None = None  # für Rückfall bei Ladefehler

        self.tray = Tray(
            describe_hotkey(config.hotkey),
            config.sound,
            config.overlay,
            paths.config_file(),
            log_file,
        )
        self.tray.quit_requested.connect(self.shutdown)
        self.tray.settings_requested.connect(self.open_settings)
        self.tray.sound_toggled.connect(self._on_sound_toggled)
        self.tray.overlay_toggled.connect(self._on_overlay_toggled)
        self.status_changed.connect(self._on_status)
        self.model_loaded.connect(self._on_model_loaded)
        self.model_failed.connect(self._on_model_failed)
        self.hotkey_captured.connect(self._on_hotkey_captured)

    def start(self) -> None:
        self.tray.show()
        self._listener = start_listener(self._on_key_press, self._on_key_release)
        self._load_model_in_background()

    # --- Tastatur (Listener-Thread) ---

    def _on_key_press(self, key: str) -> None:
        target = self._key_target
        if target is not None:
            target.press(key)

    def _on_key_release(self, key: str) -> None:
        target = self._key_target
        if target is not None:
            target.release(key)

    # --- Modell ---

    def _load_model_in_background(self) -> None:
        # Im Hintergrund: Das Icon erscheint sofort, ein bisheriges Modell arbeitet weiter.
        self.tray.set_status(Status.LOADING)
        threading.Thread(
            target=self._load_model, args=(self._config,), name="model-loader", daemon=True
        ).start()

    def _load_model(self, config: Config) -> None:
        try:
            transcriber = Transcriber(config.model, config.device, config.language)
        except Exception as exc:
            log.exception("Modell konnte nicht geladen werden")
            self.model_failed.emit(str(exc))
            return
        self.model_loaded.emit(transcriber)

    def _on_model_loaded(self, transcriber: Transcriber) -> None:
        choice = transcriber.choice
        log.info("Modell '%s' bereit (%s).", choice.name, choice.device.upper())
        if self._app is not None:  # Modellwechsel: das alte Modell erst jetzt ablösen
            self._key_target = None
            self._recorder.stop()  # falls gerade jemand mitten im Diktat war
            self._app.stop()
        # Die Sprache kann sich während des Ladens geändert haben.
        transcriber.language = whisper_language(self._config.language)
        self._config_before_model_change = None
        self._app = App(transcriber, self._recorder, on_status=self.status_changed.emit)
        self._app.start()
        self._activate_push_to_talk()
        log.info("Bereit! Halte [%s] gedrückt und sprich.", describe_hotkey(self._config.hotkey))

    def _on_model_failed(self, message: str) -> None:
        if self._app is None:  # beim Start: ohne Modell geht nichts
            QMessageBox.critical(
                None,
                TITLE,
                "Das Sprachmodell konnte nicht geladen werden:\n\n"
                f"{message}\n\n"
                "Beim ersten Start wird eine Internetverbindung für den Download benötigt.\n"
                f"Details in der Logdatei:\n{self._log_file}",
            )
            self.shutdown()
            return
        # Modellwechsel fehlgeschlagen: Das alte Modell läuft weiter, Config zurücksetzen.
        failed = self._config.model
        previous = self._config_before_model_change
        if previous is not None:
            self._save_config(replace(self._config, model=previous.model, device=previous.device))
            self._config_before_model_change = None
        self.tray.set_status(self._status)
        QMessageBox.warning(
            None,
            TITLE,
            f"Das Modell '{failed}' konnte nicht geladen werden:\n\n{message}\n\n"
            "Das bisherige Modell bleibt aktiv.",
        )

    def _activate_push_to_talk(self) -> None:
        if self._app is None:
            return
        self._push_to_talk = PushToTalk(
            parse_hotkey(self._config.hotkey),
            self._app.on_start,
            self._app.on_stop,
            self._app.on_cancel,
        )
        self._key_target = self._push_to_talk

    # --- Status, Ton, Overlay ---

    def _on_status(self, status: Status) -> None:
        tone = tone_for_transition(self._status, status)
        self._status = status
        self.tray.set_status(status)  # zuerst Icon und Overlay: play() braucht ~100 ms
        if self._config.overlay:
            self._overlay.set_status(status)
        if tone is not None:
            self._tones.play(tone)

    def _on_sound_toggled(self, enabled: bool) -> None:
        self._tones.enabled = enabled
        self._save_config(replace(self._config, sound=enabled))

    def _on_overlay_toggled(self, enabled: bool) -> None:
        self._overlay.set_status(self._status if enabled else Status.READY)
        self._save_config(replace(self._config, overlay=enabled))

    def _save_config(self, config: Config) -> None:
        self._config = config
        try:
            save_config(paths.config_file(), config)
        except OSError:
            log.exception("Einstellungen konnten nicht gespeichert werden")

    # --- Einstellungsfenster ---

    def open_settings(self) -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        downloaded = {info.name for info in MODELS if is_model_downloaded(info.name)}
        dialog = SettingsDialog(self._config, autostart.is_enabled(), list_microphones(), downloaded)
        dialog.capture_requested.connect(self._start_hotkey_capture)
        dialog.finished.connect(self._on_settings_closed)
        self._settings_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _start_hotkey_capture(self) -> None:
        # Diktieren pausieren, sonst würde der gedrückte Hotkey gleich eine Aufnahme starten.
        self._key_target = HotkeyCapture(self.hotkey_captured.emit)

    def _on_hotkey_captured(self, hotkey: str) -> None:
        self._key_target = self._push_to_talk
        if self._settings_dialog is not None:
            self._settings_dialog.set_captured_hotkey(hotkey)

    def _on_settings_closed(self, result: int) -> None:
        dialog = self._settings_dialog
        self._settings_dialog = None
        self._key_target = self._push_to_talk  # falls eine Hotkey-Aufnahme noch offen war
        if dialog is None:
            return
        if result == QDialog.DialogCode.Accepted:
            self.apply_settings(dialog.settings())
        dialog.deleteLater()

    def apply_settings(self, settings: Settings) -> None:
        old, new = self._config, settings.config
        self._save_config(new)
        log.info("Einstellungen gespeichert.")

        if settings.autostart != autostart.is_enabled():
            try:
                autostart.set_enabled(settings.autostart)
            except OSError:
                log.exception("Autostart konnte nicht geändert werden")

        self._tones.enabled = new.sound
        if not new.overlay:
            self._overlay.set_status(Status.READY)  # ausblenden
        self.tray.set_toggles(new.sound, new.overlay)
        self._recorder.microphone = new.microphone

        if new.hotkey != old.hotkey:
            self.tray.set_hotkey_label(describe_hotkey(new.hotkey))
            self._activate_push_to_talk()

        if (new.model, new.device) != (old.model, old.device):
            self._config_before_model_change = old
            self._load_model_in_background()
        elif new.language != old.language and self._app is not None:
            self._app.set_language(whisper_language(new.language))

    def shutdown(self) -> None:
        log.info("Plaudertaste wird beendet.")
        self._key_target = None
        if self._listener is not None:
            self._listener.stop()
        if self._app is not None:
            self._app.stop()
        self._overlay.hide()
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
        parse_hotkey(config.hotkey)  # früh prüfen, damit ein Tippfehler klar gemeldet wird
    except (ConfigError, ValueError) as exc:
        log.error("Konfiguration ungültig: %s (Datei: %s)", exc, config_path)
        QMessageBox.critical(
            None, TITLE, f"Die Konfiguration ist ungültig:\n\n{exc}\n\nDatei:\n{config_path}"
        )
        return 1
    log.info("Konfiguration: %s", config_path)

    controller = Controller(config, log_file)
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
