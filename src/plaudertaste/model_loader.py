"""Lädt Whisper-Modelle im Hintergrund – mit Fortschritt, Abbrechen und verständlichen Fehlern.

Kennt keine Fenster und Icons: Es meldet nur über Signale, was passiert. Was die
Oberfläche daraus macht, entscheidet der Controller (gui.py).
"""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Signal

from plaudertaste.config import Config
from plaudertaste.model_download import DownloadCancelled, DownloadFailed
from plaudertaste.network import OfflineError
from plaudertaste.transcriber import Transcriber

log = logging.getLogger(__name__)


class ModelLoader(QObject):
    # Alle Signale kommen aus Hintergrund-Threads; Qt reicht sie in den Haupt-Thread weiter.
    # object statt int: Qt-ints haben 32 Bit, large-v3 hat über 3 Milliarden Bytes.
    progress = Signal(str, object, object)  # Modell, geladene Bytes, Gesamt-Bytes
    loaded = Signal(object)  # Transcriber
    failed = Signal(str, str)  # verständliche Meldung, technische Details
    cancelled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cancel = threading.Event()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel.is_set()

    def load(self, config: Config) -> None:
        self._cancel = threading.Event()  # pro Ladevorgang ein eigenes Abbruch-Signal
        threading.Thread(
            target=self._run, args=(config, self._cancel), name="model-loader", daemon=True
        ).start()

    def cancel(self) -> None:
        """Bricht einen laufenden Download ab – der Download-Prozess wird beendet."""
        self._cancel.set()

    def _run(self, config: Config, cancel: threading.Event) -> None:
        try:
            transcriber = Transcriber(
                config.model, config.device, config.language, self.progress.emit, cancel
            )
        except DownloadCancelled:
            self.cancelled.emit()
        except OfflineError as exc:
            log.error("%s", exc)
            self.failed.emit(str(exc), "Offline-Modus aktiv")
        except DownloadFailed as exc:
            log.error("Download fehlgeschlagen: %s", exc)
            self.failed.emit(
                "Das Sprachmodell konnte nicht heruntergeladen werden. "
                "Bitte prüfe deine Internetverbindung.",
                str(exc),
            )
        except Exception as exc:
            log.exception("Modell konnte nicht geladen werden")
            self.failed.emit("Das Sprachmodell konnte nicht geladen werden.", str(exc))
        else:
            self.loaded.emit(transcriber)
