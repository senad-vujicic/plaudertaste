"""Qt-Oberfläche: verbindet Hauptfenster, Tray-Icon, Modell-Laden und Diktat-Ablauf.

Qt-Regel: Fenster und Icon dürfen nur im Haupt-Thread verändert werden. Tastatur-Listener,
Modell-Lader und Worker laufen in eigenen Threads und melden sich deshalb über Qt-Signale.
Ein Signal aus einem anderen Thread wird automatisch in den Haupt-Thread weitergereicht.
"""

from __future__ import annotations

import ctypes
import logging
import signal
import sys
import threading
from dataclasses import replace
from pathlib import Path

from pynput import keyboard
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from plaudertaste import GITHUB_REPO, __version__, autostart, paths, theme
from plaudertaste.app import MIC_UNAVAILABLE, App, Notice, Status
from plaudertaste.catalog import AUTO, MODELS, language_display
from plaudertaste.config import Config, ConfigError, load_config, save_config
from plaudertaste.devices import list_microphones
from plaudertaste.dictionary import Dictionary, DictionaryError, load_dictionary, save_dictionary
from plaudertaste.dictionary_page import DictionaryPage
from plaudertaste.history import History
from plaudertaste.hotkey import (
    UNDO_KEY,
    HotkeyCapture,
    PushToTalk,
    describe_hotkey,
    parse_hotkey,
    start_listener,
)
from plaudertaste.main_window import MainWindow, Page
from plaudertaste.model_download import DownloadCancelled, DownloadFailed, is_model_downloaded
from plaudertaste.network import OfflineError, guard
from plaudertaste.overlay import Overlay
from plaudertaste.recorder import Recorder
from plaudertaste.settings_page import DEFAULT_MICROPHONE_LABEL, Settings, SettingsPage
from plaudertaste.single_instance import acquire_single_instance_lock
from plaudertaste.sounds import TonePlayer, tone_for_transition
from plaudertaste.stats import Stats
from plaudertaste.transcriber import Transcriber
from plaudertaste.updates import Update, check_for_update
from plaudertaste.tray import Tray, make_app_icon

log = logging.getLogger(__name__)

TITLE = "Plaudertaste"
HANDS_FREE_LIMIT_MS = 5 * 60 * 1000  # Freihand-Aufnahme endet spätestens nach 5 Minuten

# Dauerhafte Probleme für die Startseite: (Überschrift, Lösungstipp)
PROBLEM_MIC_UNAVAILABLE = (
    "Kein Mikrofon verfügbar",
    "Prüfe, ob ein Mikrofon angeschlossen ist. Unter Windows-Einstellungen → Datenschutz und "
    "Sicherheit → Mikrofon muss „Desktop-Apps Zugriff auf Ihr Mikrofon erlauben“ an sein.",
)
PROBLEM_GPU_FALLBACK = (
    "NVIDIA-Grafikkarte nicht nutzbar",
    "Plaudertaste läuft auf dem Prozessor – das funktioniert, ist aber langsamer. "
    "Details stehen in der Logdatei.",
)
# Eigene Kennung für Windows: Ohne sie ordnet die Taskleiste das Fenster python.exe zu
# und zeigt dessen Icon.
APP_USER_MODEL_ID = "Plaudertaste.Plaudertaste"


def whisper_language(setting: str) -> str | None:
    """Config-Wert -> Whisper-Parameter ("auto" heißt: Whisper erkennt selbst)."""
    return None if setting == AUTO else setting


class Controller(QObject):
    status_changed = Signal(object)  # Status – aus App-Threads
    dictation_finished = Signal(str, float)  # Text, Sprechdauer – aus dem Worker-Thread
    # object statt int: Qt-ints haben 32 Bit, large-v3 hat über 3 Milliarden Bytes.
    download_progress = Signal(str, object, object)  # Modell, Bytes, Gesamt – Download-Threads
    model_loaded = Signal(object)  # Transcriber – aus dem Lade-Thread
    model_failed = Signal(str, str)  # verständliche Meldung, technische Details
    notice = Signal(object)  # Notice – aus App-Threads
    model_cancelled = Signal()
    hotkey_captured = Signal(str)  # aus dem Tastatur-Thread
    hands_free_started = Signal()  # aus dem Tastatur-Thread
    update_available = Signal(object)  # Update – aus dem Update-Thread
    connection_made = Signal(object)  # Connection – aus beliebigen Threads

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
        self._model_text = "wird geladen …"
        self._model_text_before_change = self._model_text
        self._download_cancel = threading.Event()
        self._recorder = Recorder(config.microphone)
        self._tones = TonePlayer(config.sound)
        self._overlay = Overlay(level_source=lambda: self._recorder.level)
        self._history = History()
        self._stats = Stats(paths.stats_file())
        self._config_before_model_change: Config | None = None  # für Rückfall bei Ladefehler
        self._tray_hint_shown = False
        self._problems: dict[str, tuple[str, str]] = {}  # bestehende Probleme für die Startseite
        self._dictionary = Dictionary()

        self.tray = Tray(
            describe_hotkey(config.hotkey),
            config.sound,
            config.overlay,
            paths.config_file(),
            log_file,
        )
        self.settings_page = SettingsPage()
        self.dictionary_page = DictionaryPage()
        self.window = MainWindow(
            make_app_icon(), self.settings_page, self.dictionary_page, self._history, self._stats
        )

        self.tray.quit_requested.connect(self.shutdown)
        self.tray.open_requested.connect(lambda: self.show_window(Page.START))
        self.tray.settings_requested.connect(lambda: self.show_window(Page.SETTINGS))
        self.tray.sound_toggled.connect(self._on_sound_toggled)
        self.tray.overlay_toggled.connect(self._on_overlay_toggled)
        self.window.hidden_to_tray.connect(self._on_window_hidden)
        self.window.sidebar.currentRowChanged.connect(self._on_page_changed)
        self.settings_page.save_requested.connect(self.apply_settings)
        self.dictionary_page.changed.connect(self._on_dictionary_changed)
        self.settings_page.capture_requested.connect(self._start_hotkey_capture)
        self.settings_page.capture_cancelled.connect(self._stop_hotkey_capture)
        self.status_changed.connect(self._on_status)
        self.notice.connect(self._on_notice)
        self.dictation_finished.connect(self._on_dictation_finished)
        self.download_progress.connect(self._on_download_progress)
        self.model_loaded.connect(self._on_model_loaded)
        self.model_failed.connect(self._on_model_failed)
        self.model_cancelled.connect(self._on_model_cancelled)
        self.window.download_banner.cancel_requested.connect(self.cancel_download)
        self.hotkey_captured.connect(self._on_hotkey_captured)
        self.hands_free_started.connect(self._on_hands_free_started)
        self.update_available.connect(self._on_update_available)
        self.connection_made.connect(lambda _: self._refresh_connections())
        guard.subscribe(self.connection_made.emit)
        guard.offline = config.offline_mode
        # Notstopp, falls eine Freihand-Aufnahme vergessen wird
        self._hands_free_timer = QTimer(self, singleShot=True, interval=HANDS_FREE_LIMIT_MS)
        self._hands_free_timer.timeout.connect(self._stop_forgotten_hands_free)

        self._load_dictionary()
        self._refresh_start_page()
        self.window.start_page.set_status(Status.LOADING)
        self.window.refresh()

    def start(self, show_window: bool) -> None:
        self.tray.show()
        if show_window:
            self.show_window(Page.START)
        self._refresh_autostart_entry()
        self._listener = start_listener(self._on_key_press, self._on_key_release, self._swallow)
        self._load_model_in_background()
        if self._config.check_updates and not self._config.offline_mode:
            threading.Thread(target=self._check_for_update, name="update-check", daemon=True).start()

    def _refresh_connections(self) -> None:
        self.settings_page.set_connections(guard.connections)

    # --- Update-Hinweis ---

    def _check_for_update(self) -> None:
        update = check_for_update(__version__, GITHUB_REPO)
        if update is not None:
            self.update_available.emit(update)

    def _on_update_available(self, update: Update) -> None:
        log.info("Neue Version verfügbar: %s", update.version)
        self.window.start_page.show_update(update.version, update.url)
        self.tray.showMessage(
            TITLE,
            f"Neue Version {update.version} verfügbar – Details auf der Startseite.",
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )

    def show_window(self, page: Page) -> None:
        if page is Page.SETTINGS and self.window.current_page() is Page.SETTINGS:
            self._load_settings_page()  # Seitenwechsel lädt sonst selbst, hier gibt es keinen
        self.window.show_page(page)

    # --- Tastatur (Listener-Thread) ---

    # Ein Fehler hier würde den Tastatur-Listener still beenden – und der Hotkey wäre
    # bis zum Neustart tot. Deshalb abfangen und protokollieren.

    def _on_key_press(self, key: str) -> None:
        target = self._key_target
        if target is None:
            return
        try:
            if isinstance(target, PushToTalk) and self._app is not None:
                if not target.is_hotkey_key(key) and key != UNDO_KEY:
                    # Eigenes Tippen: Der Cursor steht evtl. woanders – Rückgängig sperren.
                    self._app.forget_last_dictation()
            target.press(key)
        except Exception:
            log.exception("Fehler bei Tastendruck")

    def _swallow(self, key: str) -> bool:
        """Rücktaste beim gehaltenen Hotkey dem Zielprogramm vorenthalten."""
        target = self._key_target
        return isinstance(target, PushToTalk) and target.wants_to_swallow(key)

    def _on_key_release(self, key: str) -> None:
        target = self._key_target
        if target is not None:
            try:
                target.release(key)
            except Exception:
                log.exception("Fehler beim Loslassen einer Taste")

    # --- Modell ---

    def _load_model_in_background(self) -> None:
        # Im Hintergrund: Fenster und Icon reagieren sofort, ein altes Modell arbeitet weiter.
        self.tray.set_status(Status.LOADING)
        self.window.start_page.set_status(Status.LOADING)
        self._download_cancel = threading.Event()  # pro Ladevorgang ein eigenes Signal
        threading.Thread(
            target=self._load_model,
            args=(self._config, self._download_cancel),
            name="model-loader",
            daemon=True,
        ).start()

    def _load_model(self, config: Config, cancel: threading.Event) -> None:
        try:
            transcriber = Transcriber(
                config.model, config.device, config.language, self.download_progress.emit, cancel
            )
        except DownloadCancelled:
            self.model_cancelled.emit()
            return
        except OfflineError as exc:
            log.error("%s", exc)
            self.model_failed.emit(str(exc), "Offline-Modus aktiv")
            return
        except DownloadFailed as exc:
            log.error("Download fehlgeschlagen: %s", exc)
            self.model_failed.emit(
                "Das Sprachmodell konnte nicht heruntergeladen werden. "
                "Bitte prüfe deine Internetverbindung.",
                str(exc),
            )
            return
        except Exception as exc:
            log.exception("Modell konnte nicht geladen werden")
            self.model_failed.emit("Das Sprachmodell konnte nicht geladen werden.", str(exc))
            return
        self.model_loaded.emit(transcriber)

    def _on_download_progress(self, model: str, done: int, total: int) -> None:
        self.window.download_banner.show_progress(model, done, total)
        self.tray.set_download_progress(model, done * 100 // total if total else 0)
        if done >= total:
            log.info("Modell '%s' heruntergeladen.", model)

    def _on_model_loaded(self, transcriber: Transcriber) -> None:
        self.window.download_banner.hide()
        choice = transcriber.choice
        log.info("Modell '%s' bereit (%s).", choice.name, choice.device.upper())
        if self._app is not None:  # Modellwechsel: das alte Modell erst jetzt ablösen
            self._key_target = None
            self._recorder.stop()  # falls gerade jemand mitten im Diktat war
            self._app.stop()
        # Die Sprache kann sich während des Ladens geändert haben.
        transcriber.language = whisper_language(self._config.language)
        self._config_before_model_change = None
        self._model_text = f"{choice.name} · {'GPU' if choice.device == 'cuda' else 'CPU'}"
        self._set_problem("gpu", PROBLEM_GPU_FALLBACK if transcriber.gpu_fallback else None)
        self._refresh_start_page()
        self._app = App(
            transcriber,
            self._recorder,
            on_status=self.status_changed.emit,
            on_dictation=self.dictation_finished.emit,
            on_notice=self.notice.emit,
            dictionary=self._dictionary,
            voice_commands=self._config.voice_commands,
            remove_fillers=self._config.remove_fillers,
        )
        self._app.start()
        self._activate_push_to_talk()
        log.info("Bereit! Halte [%s] gedrückt und sprich.", describe_hotkey(self._config.hotkey))

    def _on_model_failed(self, message: str, details: str) -> None:
        self.window.download_banner.hide()
        if self._app is None:  # beim Start: ohne Modell geht nichts
            QMessageBox.critical(
                self.window,
                TITLE,
                f"{message}\n\nOhne Sprachmodell kann Plaudertaste nicht diktieren und wird "
                "beendet. Starte es danach einfach neu.\n\n"
                f"Technische Details: {details}\nLogdatei: {self._log_file}",
            )
            self.shutdown()
            return
        self._restore_previous_model()
        QMessageBox.warning(
            self.window,
            TITLE,
            f"{message}\n\nDas bisherige Modell bleibt aktiv.\n\nTechnische Details: {details}",
        )

    def cancel_download(self) -> None:
        if self._app is None:  # erster Start: ohne Modell kann Plaudertaste nicht diktieren
            answer = QMessageBox.question(
                self.window,
                TITLE,
                "Ohne Sprachmodell kann Plaudertaste nicht diktieren.\n\n"
                "Download abbrechen und Plaudertaste beenden?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.window.download_banner.cancel_button.setEnabled(False)  # kein Doppelklick
        self._download_cancel.set()

    def _on_model_cancelled(self) -> None:
        log.info("Download abgebrochen.")
        self.window.download_banner.hide()
        if self._app is None:
            self.shutdown()
            return
        self._restore_previous_model()

    def _restore_previous_model(self) -> None:
        """Modellwechsel gescheitert oder abgebrochen: Das alte Modell läuft weiter."""
        previous = self._config_before_model_change
        if previous is not None:
            self._save_config(replace(self._config, model=previous.model, device=previous.device))
            self._config_before_model_change = None
        self._model_text = self._model_text_before_change
        self._refresh_start_page()
        self.tray.set_status(self._status)
        self.window.start_page.set_status(self._status)

    def _activate_push_to_talk(self) -> None:
        if self._app is None:
            return
        self._push_to_talk = PushToTalk(
            parse_hotkey(self._config.hotkey),
            self._app.on_start,
            self._app.on_stop,
            self._app.on_cancel,
            on_hands_free=self.hands_free_started.emit,
            on_undo=self._app.on_undo,
        )
        self._key_target = self._push_to_talk

    # --- Status, Ton, Overlay, Verlauf, Statistik ---

    def _on_status(self, status: Status) -> None:
        tone = tone_for_transition(self._status, status)
        self._status = status
        if status is Status.RECORDING:  # Aufnahme klappt -> Mikrofon-Probleme neu bewerten
            self._set_problem("mic", None)
            missing = self._recorder.fell_back_to_default
            self._set_problem("mic_missing", self._missing_microphone_problem() if missing else None)
        self.tray.set_status(status)  # zuerst Anzeige: play() braucht ~100 ms
        self.window.start_page.set_status(status)
        if status is not Status.RECORDING:
            self._hands_free_timer.stop()
            self._overlay.set_hands_free(False)
        if self._config.overlay:
            self._overlay.set_status(status)
        if tone is not None:
            self._tones.play(tone)

    def _on_hands_free_started(self) -> None:
        log.info("Freihand-Aufnahme gestartet.")
        self._overlay.set_hands_free(True)
        self._hands_free_timer.start()

    def _stop_forgotten_hands_free(self) -> None:
        if self._push_to_talk is not None and self._push_to_talk.is_hands_free:
            log.info("Freihand-Aufnahme nach %d min automatisch beendet.", HANDS_FREE_LIMIT_MS // 60000)
            self._push_to_talk.stop_hands_free()

    def _on_notice(self, notice: Notice) -> None:
        """Problem während des Diktierens: rot im Overlay, ernste zusätzlich als Windows-Hinweis.
        Ein Fehlerfenster wäre hier falsch – es nähme den Fokus, das nächste Diktat landete darin."""
        log.info("Hinweis an Nutzer: %s", notice.text)
        if self._config.overlay:
            self._overlay.show_message(notice.text)
        if notice.serious:
            self.tray.showMessage(TITLE, notice.text, QSystemTrayIcon.MessageIcon.Warning, 5000)
        if notice is MIC_UNAVAILABLE:
            self._set_problem("mic", PROBLEM_MIC_UNAVAILABLE)

    def _missing_microphone_problem(self) -> tuple[str, str]:
        return (
            f"Gewähltes Mikrofon „{self._config.microphone}“ nicht gefunden",
            "Plaudertaste nutzt solange den Windows-Standard. Stecke das Mikrofon ein oder "
            "wähle in den Einstellungen ein anderes.",
        )

    def _set_problem(self, key: str, problem: tuple[str, str] | None) -> None:
        """Dauerhaftes Problem auf der Startseite setzen (None = behoben)."""
        is_new = problem is not None and key not in self._problems
        if problem is None:
            self._problems.pop(key, None)
        else:
            self._problems[key] = problem
        self.window.start_page.set_problems(list(self._problems.values()))
        if is_new and key != "mic":  # "mic" meldet bereits _on_notice
            self.tray.showMessage(TITLE, problem[0], QSystemTrayIcon.MessageIcon.Warning, 5000)

    # --- Wörterbuch ---

    def _load_dictionary(self) -> None:
        path = paths.dictionary_file()
        try:
            self._dictionary = load_dictionary(path)
        except DictionaryError as exc:
            # Kaputte Datei aufheben statt beim nächsten Speichern zu überschreiben.
            backup = path.with_suffix(".defekt.toml")
            path.replace(backup)
            log.error("%s – gesichert als %s", exc, backup)
            self._set_problem(
                "dictionary",
                ("Wörterbuch-Datei fehlerhaft", f"Sie wurde als „{backup.name}“ gesichert, "
                 "das Wörterbuch startet leer. Details in der Logdatei."),
            )
        self.dictionary_page.set_dictionary(self._dictionary)

    def _on_dictionary_changed(self, dictionary: Dictionary) -> None:
        self._dictionary = dictionary
        if self._app is not None:
            self._app.set_dictionary(dictionary)
        try:
            save_dictionary(paths.dictionary_file(), dictionary)
        except OSError:
            log.exception("Wörterbuch konnte nicht gespeichert werden")
            return
        self._set_problem("dictionary", None)
        self.dictionary_page.show_saved()

    def _on_dictation_finished(self, text: str, seconds: float) -> None:
        entry = self._history.add(text, seconds)
        self.window.start_page.set_last_dictation(entry)
        try:
            self._stats.record(text, seconds)
        except OSError:
            log.exception("Statistik konnte nicht gespeichert werden")
        self.window.refresh()
        self.window.start_page.set_today(self._stats.today())

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

    def _refresh_start_page(self) -> None:
        config = self._config
        self.window.start_page.set_info(
            hotkey=describe_hotkey(config.hotkey),
            model=self._model_text,
            language=language_display(config.language),
            microphone=config.microphone or DEFAULT_MICROPHONE_LABEL,
        )
        self.window.start_page.set_today(self._stats.today())

    # --- Fenster und Einstellungen ---

    def _on_window_hidden(self) -> None:
        if not self._tray_hint_shown:  # nur beim ersten Mal erklären
            self._tray_hint_shown = True
            self.tray.showMessage(
                TITLE,
                "Plaudertaste läuft im Hintergrund weiter. Beenden über Rechtsklick → Beenden.",
                self.tray.icon(),
            )

    def _on_page_changed(self, row: int) -> None:
        if row == Page.SETTINGS:
            self._load_settings_page()

    def _load_settings_page(self) -> None:
        downloaded = {info.name for info in MODELS if is_model_downloaded(info.name)}
        self.settings_page.load(
            self._config, autostart.is_enabled(), list_microphones(), downloaded
        )
        self._refresh_connections()

    def _start_hotkey_capture(self) -> None:
        # Diktieren pausieren, sonst würde der gedrückte Hotkey gleich eine Aufnahme starten.
        self._key_target = HotkeyCapture(self.hotkey_captured.emit)

    def _stop_hotkey_capture(self) -> None:
        self._key_target = self._push_to_talk

    def _on_hotkey_captured(self, hotkey: str) -> None:
        self._stop_hotkey_capture()
        self.settings_page.set_captured_hotkey(hotkey)

    def _refresh_autostart_entry(self) -> None:
        """Einen vorhandenen Autostart-Eintrag auf den aktuellen Befehl bringen
        (z. B. nach einem Update oder wenn die .exe verschoben wurde)."""
        try:
            if autostart.is_enabled():
                autostart.set_enabled(True)
        except OSError:
            log.exception("Autostart-Eintrag konnte nicht aktualisiert werden")

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
        if new.offline_mode != old.offline_mode:
            guard.offline = new.offline_mode
            log.info("Offline-Modus %s.", "an" if new.offline_mode else "aus")
        if self._app is not None:
            self._app.voice_commands = new.voice_commands
            self._app.remove_fillers = new.remove_fillers
        if new.microphone != old.microphone:
            self._set_problem("mic_missing", None)  # wird bei der nächsten Aufnahme neu geprüft

        if new.hotkey != old.hotkey:
            self.tray.set_hotkey_label(describe_hotkey(new.hotkey))
            self._activate_push_to_talk()

        if (new.model, new.device) != (old.model, old.device):
            self._config_before_model_change = old
            self._model_text_before_change = self._model_text
            self._model_text = "wird geladen …"
            self._load_model_in_background()
        elif new.language != old.language and self._app is not None:
            self._app.set_language(whisper_language(new.language))

        self._refresh_start_page()
        self._load_settings_page()  # zeigt den neuen gespeicherten Stand
        self.settings_page.show_saved()

    def shutdown(self) -> None:
        log.info("Plaudertaste wird beendet.")
        self._download_cancel.set()  # ein laufender Download-Prozess wird beendet
        self._key_target = None
        if self._listener is not None:
            self._listener.stop()
        if self._app is not None:
            self._app.stop()
        self._overlay.hide()
        self.tray.hide()
        QApplication.quit()


def run(log_file: Path, show_window: bool = True) -> int:
    guard.install()  # als Allererstes: ab jetzt läuft jede Verbindung über den Wächter
    if sys.platform == "win32":  # muss vor dem ersten Fenster passieren
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    qapp = QApplication(sys.argv)
    qapp.setApplicationName(TITLE)
    qapp.setWindowIcon(make_app_icon())
    theme.apply_theme(qapp)
    qapp.setQuitOnLastWindowClosed(False)  # läuft im Infobereich weiter, wenn das Fenster zu ist

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
    controller.start(show_window)

    # Strg+C in der Konsole: Qt blockiert Python-Signale, solange die Ereignisschleife
    # läuft. Ein kurzer Timer gibt Python regelmäßig die Gelegenheit, sie zu verarbeiten.
    signal.signal(signal.SIGINT, lambda *_: controller.shutdown())
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start(200)

    exit_code = qapp.exec()
    lock.unlock()
    return exit_code
