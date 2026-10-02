"""Verbindet Hotkey, Aufnahme, Spracherkennung und Einfügen zu einem Ablauf."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import numpy as np

from plaudertaste.dictionary import Dictionary
from plaudertaste.fillers import remove_fillers
from plaudertaste.paster import erase_before_cursor, paste_text
from plaudertaste.recorder import Recorder, RecorderError
from plaudertaste.transcriber import Transcriber
from plaudertaste.voice_commands import apply_voice_commands

log = logging.getLogger(__name__)

MIN_DURATION_S = 0.3  # kürzere Aufnahmen gelten als versehentliches Antippen
# Spitzenpegel darunter = praktisch absolute Stille: Mikrofon vermutlich stummgeschaltet.
# (Normales Raumrauschen liegt deutlich darüber, gemessen am Volt 2: ~0,009.)
SILENCE_PEAK = 0.001


class Status(Enum):
    LOADING = "Modell wird geladen …"
    READY = "Bereit"
    RECORDING = "Aufnahme läuft"
    PROCESSING = "Wird verarbeitet …"


@dataclass(frozen=True)
class Notice:
    """Ein Problem, das dem Nutzer gezeigt werden soll."""

    text: str
    serious: bool = False  # ernst = zusätzlich als Windows-Benachrichtigung


MIC_UNAVAILABLE = Notice(
    "Kein Mikrofon verfügbar – ist eins angeschlossen und für Apps freigegeben?", serious=True
)
SILENT_MICROPHONE = Notice("Kein Ton vom Mikrofon – ist es stummgeschaltet?", serious=True)
NOTHING_UNDERSTOOD = Notice("Nichts verstanden – bitte etwas länger oder deutlicher sprechen.")
PASTE_FAILED = Notice(
    "Text konnte nicht eingefügt werden – er liegt im Verlauf zum Kopieren.", serious=True
)
PROCESSING_FAILED = Notice("Fehler bei der Spracherkennung – Details in der Logdatei.", serious=True)
UNDONE = Notice("Letztes Diktat gelöscht.")
NOTHING_TO_UNDO = Notice("Nichts zum Rückgängigmachen – seit dem letzten Diktat wurde getippt.")

_UNDO = object()  # Auftrag in der Warteschlange: letztes Diktat löschen


class App:
    """Die Hotkey-Callbacks laufen im Tastatur-Thread und müssen sofort zurückkehren.

    Die langsame Arbeit (Spracherkennung, Einfügen) erledigt ein eigener Worker-Thread,
    der Aufnahmen über eine Warteschlange bekommt. Meldungen, aus beliebigen Threads:
    `on_status` (Statuswechsel), `on_dictation` (Text und Sprechdauer eines Diktats,
    auch wenn das Einfügen scheiterte) und `on_notice` (Probleme für den Nutzer).
    """

    def __init__(
        self,
        transcriber: Transcriber,
        recorder: Recorder,
        paste: Callable[[str], None] = paste_text,
        erase: Callable[[int], None] = erase_before_cursor,
        on_status: Callable[[Status], None] = lambda status: None,
        on_dictation: Callable[[str, float], None] = lambda text, seconds: None,
        on_notice: Callable[[Notice], None] = lambda notice: None,
        dictionary: Dictionary = Dictionary(),
        voice_commands: bool = True,
        remove_fillers: bool = True,
    ) -> None:
        self._transcriber = transcriber
        self._recorder = recorder
        self._paste = paste
        self._erase = erase
        # Länge des zuletzt eingefügten Textes – 0, wenn Rückgängig nicht (mehr) sicher ist
        self._undoable_length = 0
        self._on_status = on_status
        self._on_dictation = on_dictation
        self._on_notice = on_notice
        self._dictionary = Dictionary()
        self.set_dictionary(dictionary)
        self.voice_commands = voice_commands
        self.remove_fillers = remove_fillers
        self._jobs: queue.Queue[np.ndarray | object | None] = queue.Queue()
        self._worker = threading.Thread(target=self._work, name="transcriber", daemon=True)
        # Status ergibt sich aus "nimmt gerade auf?" und "wie viele Aufnahmen warten?",
        # damit eine neue Aufnahme nicht vom Ende der vorherigen überschrieben wird.
        self._state_lock = threading.Lock()
        self._recording = False
        self._pending = 0

    def start(self) -> None:
        self._worker.start()
        self._publish_status()

    def set_language(self, language: str | None) -> None:
        """Sprache wechseln, ohne das Modell neu zu laden (None = automatisch erkennen)."""
        self._transcriber.language = language

    def set_dictionary(self, dictionary: Dictionary) -> None:
        """Begriffe gehen als Hinweis an Whisper, Ersetzungen gelten nach der Erkennung."""
        self._dictionary = dictionary
        self._transcriber.hotwords = dictionary.hotwords()

    def stop(self) -> None:
        """Arbeitet noch wartende Aufnahmen ab und beendet dann den Worker."""
        self._jobs.put(None)
        self._worker.join()

    # --- Hotkey-Callbacks (Tastatur-Thread) ---

    def on_start(self) -> None:
        try:
            self._recorder.start()
        except RecorderError as exc:
            log.error("%s", exc)
            self._on_notice(MIC_UNAVAILABLE)
            return
        self._update(recording=True)
        log.info("Aufnahme läuft …")

    def on_stop(self) -> None:
        audio = self._recorder.stop()
        duration = audio.size / self._recorder.sample_rate
        if duration < MIN_DURATION_S:
            self._update(recording=False)
            log.info("Zu kurz (%.1f s) – ignoriert.", duration)
            return
        log.info("Verarbeite %.1f s Audio …", duration)
        self._update(recording=False, pending_delta=1)
        self._jobs.put(audio)

    def on_undo(self) -> None:
        """Hotkey + Rücktaste: Das Löschen übernimmt der Worker, nach allen offenen Diktaten."""
        self._jobs.put(_UNDO)

    def forget_last_dictation(self) -> None:
        """Nach eigenem Tippen steht der Cursor evtl. woanders – dann nichts mehr löschen."""
        self._undoable_length = 0

    def on_cancel(self) -> None:
        self._recorder.stop()
        self._update(recording=False)
        log.info("Abgebrochen (andere Taste gedrückt).")

    # --- Worker-Thread ---

    def _work(self) -> None:
        while (job := self._jobs.get()) is not None:
            if job is _UNDO:
                self._undo_last()
            else:
                self._process(job)  # type: ignore[arg-type]
                self._update(pending_delta=-1)

    def _undo_last(self) -> None:
        if not self._undoable_length:
            self._on_notice(NOTHING_TO_UNDO)
            return
        try:
            self._erase(self._undoable_length)
        except Exception:
            log.exception("Rückgängig fehlgeschlagen")
            return
        log.info("Letztes Diktat gelöscht (%d Zeichen).", self._undoable_length)
        self._undoable_length = 0
        self._on_notice(UNDONE)

    def _process(self, audio: np.ndarray) -> None:
        started = time.perf_counter()
        try:
            text = self._transcriber.transcribe(audio)
        except Exception:
            # Ein Fehler bei einer Aufnahme darf das Tool nicht beenden.
            log.exception("Fehler bei der Spracherkennung")
            self._on_notice(PROCESSING_FAILED)
            return
        if not text:
            silent = float(np.abs(audio).max()) < SILENCE_PEAK
            log.info("Kein Text erkannt (%s).", "Stille" if silent else "unverständlich")
            self._on_notice(SILENT_MICROPHONE if silent else NOTHING_UNDERSTOOD)
            return
        # Reihenfolge: erst Füllwörter weg, dann Sprachbefehle, zuletzt das eigene Wörterbuch.
        if self.remove_fillers:
            text = remove_fillers(text)
        if self.voice_commands:
            text = apply_voice_commands(text)
        text = self._dictionary.apply(text)
        if not text:  # bestand nur aus Füllwörtern ("Ähm.") – nichts einzufügen
            log.info("Nur Füllwörter erkannt – nichts eingefügt.")
            return
        # Leerzeichen trennt aufeinanderfolgende Diktate – nicht aber nach einem Zeilenumbruch.
        separator = "" if text.endswith("\n") else " "
        try:
            self._paste(text + separator)
        except Exception:
            log.exception("Einfügen fehlgeschlagen")
            self._on_notice(PASTE_FAILED)
            self._undoable_length = 0
        else:
            self._undoable_length = len(text + separator)
            # Datenschutz: nur die Länge loggen, nie den diktierten Text.
            log.info("Eingefügt: %d Zeichen in %.2f s", len(text), time.perf_counter() - started)
        # Auch bei gescheitertem Einfügen: Der Text soll im Verlauf zu finden sein.
        self._on_dictation(text, audio.size / self._recorder.sample_rate)

    # --- Status ---

    def _update(self, recording: bool | None = None, pending_delta: int = 0) -> None:
        with self._state_lock:
            if recording is not None:
                self._recording = recording
            self._pending += pending_delta
            self._publish_status_locked()

    def _publish_status(self) -> None:
        with self._state_lock:
            self._publish_status_locked()

    def _publish_status_locked(self) -> None:
        # Berechnen und Melden unter derselben Sperre: So kann eine veraltete Meldung
        # aus einem anderen Thread nie nach einer neueren ankommen.
        if self._recording:
            status = Status.RECORDING
        elif self._pending:
            status = Status.PROCESSING
        else:
            status = Status.READY
        self._on_status(status)
