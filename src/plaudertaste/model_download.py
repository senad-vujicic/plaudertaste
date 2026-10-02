"""Whisper-Modell herunterladen – mit Fortschritt in Bytes und Abbrechen-Möglichkeit.

faster-whisper lädt Modelle selbst, schaltet dabei aber jede Fortschrittsanzeige ab.
Wir laden deshalb dieselben Dateien in denselben Cache selbst herunter und reichen
faster-whisper danach nur noch den lokalen Pfad.

Der Download läuft in einem eigenen Prozess: Hugging Face lädt intern (Xet, in Rust)
weiter, selbst wenn Python-Code abbrechen will. Einen Prozess dagegen kann das
Betriebssystem jederzeit zuverlässig beenden.
"""

from __future__ import annotations

import multiprocessing
import queue
import threading
from collections.abc import Callable
from typing import Any, Protocol

from huggingface_hub import snapshot_download
from tqdm.auto import tqdm

from plaudertaste.models import model_info
from plaudertaste.network import OfflineError, guard

# Dieselbe Dateiauswahl wie faster_whisper.download_model
ALLOW_PATTERNS = [
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
]
POLL_INTERVAL_S = 0.2  # so oft wird auf "Abbrechen" geprüft

ProgressCallback = Callable[[str, int, int], None]  # (Modellname, geladene Bytes, Gesamt-Bytes)
DownloadTarget = Callable[[str, Any], None]  # (repo_id, Nachrichten-Warteschlange)


class DownloadCancelled(Exception):
    """Der Download wurde auf Wunsch abgebrochen."""


class DownloadFailed(Exception):
    """Der Download ist fehlgeschlagen (z. B. keine Internetverbindung)."""


class ByteSink(Protocol):
    def add(self, n: int) -> None: ...


class ProgressCounter:
    """Zählt geladene Bytes und meldet höchstens einmal pro Prozentpunkt."""

    def __init__(self, total_bytes: int, on_progress: Callable[[int, int], None]) -> None:
        self.total = total_bytes
        self._on_progress = on_progress
        self._done = 0
        self._last_percent = -1
        self._lock = threading.Lock()

    def add(self, n: int) -> None:
        with self._lock:
            # Die Größe aus dem Katalog ist gerundet – nie über 100 % melden.
            self._done = min(self._done + n, self.total)
            percent = self._done * 100 // self.total
            if percent == self._last_percent:
                return
            self._last_percent = percent
            done = self._done
        self._on_progress(done, self.total)

    def finish(self) -> None:
        with self._lock:
            if self._last_percent == 100:  # schon gemeldet (Modell größer als geschätzt)
                return
            self._done = self.total
            self._last_percent = 100
        self._on_progress(self.total, self.total)


def counting_tqdm(sink: ByteSink) -> type[tqdm]:
    """Eine tqdm-Klasse, die nichts anzeigt, aber heruntergeladene Bytes mitzählt.

    Hugging Face meldet beim Xet-Verfahren Bytes zweimal: beim Herunterladen und beim
    Zusammensetzen ("Reconstructing"). Gezählt wird nur das Herunterladen.
    """

    class CountingTqdm(tqdm):  # type: ignore[misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["disable"] = True  # nichts in die Konsole schreiben
            super().__init__(*args, **kwargs)
            description = kwargs.get("desc") or ""
            self._counts_bytes = kwargs.get("unit") == "B" and not description.startswith(
                "Reconstructing"
            )

        def update(self, n: float | None = 1) -> bool | None:
            if self._counts_bytes and n:
                sink.add(int(n))
            return super().update(n)

    return CountingTqdm


class _QueueSink:
    def __init__(self, messages: Any) -> None:
        self._messages = messages

    def add(self, n: int) -> None:
        self._messages.put(("bytes", n))


def download_in_child(repo_id: str, messages: Any) -> None:
    """Läuft im eigenen Prozess: lädt herunter und meldet alles über die Warteschlange."""
    try:
        path = snapshot_download(
            repo_id, allow_patterns=ALLOW_PATTERNS, tqdm_class=counting_tqdm(_QueueSink(messages))
        )
    except Exception as exc:
        messages.put(("error", f"{type(exc).__name__}: {exc}"))
    else:
        messages.put(("done", path))


def download_in_process(
    repo_id: str,
    sink: ByteSink,
    cancel: threading.Event,
    target: DownloadTarget = download_in_child,
) -> str:
    """Startet den Download-Prozess und wartet darauf – bricht ab, sobald `cancel` gesetzt ist."""
    context = multiprocessing.get_context("spawn")  # unter Windows ohnehin der Standard
    messages = context.Queue()
    process = context.Process(target=target, args=(repo_id, messages), daemon=True)
    process.start()
    try:
        while True:
            if cancel.is_set():
                raise DownloadCancelled()
            try:
                kind, value = messages.get(timeout=POLL_INTERVAL_S)
            except queue.Empty:
                if process.is_alive():
                    continue
                try:  # letzte Nachricht kann knapp nach dem Prozessende eintreffen
                    kind, value = messages.get(timeout=1)
                except queue.Empty:
                    raise DownloadFailed("Der Download wurde unerwartet beendet.") from None
            if kind == "bytes":
                sink.add(value)
            elif kind == "done":
                return value
            else:
                raise DownloadFailed(value)
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        messages.close()


def is_cached(name: str) -> str | None:
    """Pfad zum Modell, falls es schon lokal vorliegt – sonst None. Lädt nichts herunter."""
    from faster_whisper import download_model  # schwerer Import, nur im Hauptprozess

    try:
        return download_model(name, local_files_only=True)
    except Exception:  # huggingface_hub meldet "nicht im Cache" mit eigenen Fehlertypen
        return None


def is_model_downloaded(name: str) -> bool:
    return is_cached(name) is not None


def ensure_model(
    name: str,
    on_progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> str:
    """Lokaler Pfad zum Modell – lädt es vorher herunter, falls es noch fehlt."""
    cached = is_cached(name)
    if cached is not None:
        return cached
    if guard.offline:
        raise OfflineError(
            f"Das Modell „{name}“ ist nicht heruntergeladen, und im Offline-Modus sind "
            "keine Downloads möglich. Schalte den Offline-Modus kurz aus oder wähle ein "
            "heruntergeladenes Modell."
        )
    info = model_info(name)
    # Der Download läuft in einem eigenen Prozess, den der Wächter nicht sieht – deshalb
    # hier selbst ins Netzwerk-Protokoll eintragen.
    guard.record("huggingface.co", "Modell-Download")
    report = on_progress or (lambda model, done, total: None)
    counter = ProgressCounter(
        info.size_mb * 1_000_000, lambda done, total: report(name, done, total)
    )
    path = download_in_process(info.repo_id, counter, cancel or threading.Event())
    counter.finish()
    return path
