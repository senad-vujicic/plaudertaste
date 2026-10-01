"""Verbindet Hotkey, Aufnahme, Spracherkennung und Einfügen zu einem Ablauf."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable

import numpy as np

from plaudertaste.paster import paste_text
from plaudertaste.recorder import Recorder, RecorderError
from plaudertaste.transcriber import Transcriber

log = logging.getLogger(__name__)

MIN_DURATION_S = 0.3  # kürzere Aufnahmen gelten als versehentliches Antippen


class App:
    """Die Hotkey-Callbacks laufen im Tastatur-Thread und müssen sofort zurückkehren.

    Die langsame Arbeit (Spracherkennung, Einfügen) erledigt ein eigener Worker-Thread,
    der Aufnahmen über eine Warteschlange bekommt.
    """

    def __init__(
        self,
        transcriber: Transcriber,
        recorder: Recorder,
        paste: Callable[[str], None] = paste_text,
    ) -> None:
        self._transcriber = transcriber
        self._recorder = recorder
        self._paste = paste
        self._jobs: queue.Queue[np.ndarray | None] = queue.Queue()
        self._worker = threading.Thread(target=self._work, name="transcriber", daemon=True)

    def start(self) -> None:
        self._worker.start()

    def stop(self) -> None:
        """Arbeitet noch wartende Aufnahmen ab und beendet dann den Worker."""
        self._jobs.put(None)
        self._worker.join()

    # --- Hotkey-Callbacks (Tastatur-Thread) ---

    def on_start(self) -> None:
        try:
            self._recorder.start()
            log.info("● Aufnahme läuft …")
        except RecorderError as exc:
            log.error("%s", exc)

    def on_stop(self) -> None:
        audio = self._recorder.stop()
        duration = audio.size / self._recorder.sample_rate
        if duration < MIN_DURATION_S:
            log.info("Zu kurz (%.1f s) – ignoriert.", duration)
            return
        log.info("Verarbeite %.1f s Audio …", duration)
        self._jobs.put(audio)

    def on_cancel(self) -> None:
        self._recorder.stop()
        log.info("Abgebrochen (andere Taste gedrückt).")

    # --- Worker-Thread ---

    def _work(self) -> None:
        while (audio := self._jobs.get()) is not None:
            self._process(audio)

    def _process(self, audio: np.ndarray) -> None:
        try:
            started = time.perf_counter()
            text = self._transcriber.transcribe(audio)
            if not text:
                log.info("Kein Text erkannt.")
                return
            self._paste(text)
            log.info("Eingefügt (%.2f s): %s", time.perf_counter() - started, text)
        except Exception:
            # Ein Fehler bei einer Aufnahme darf das Tool nicht beenden.
            log.exception("Fehler bei der Verarbeitung")
