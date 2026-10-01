"""Mikrofon-Aufnahme im Format, das Whisper erwartet (16 kHz, mono, float32)."""

from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000


class RecorderError(Exception):
    """Das Mikrofon konnte nicht geöffnet werden."""


class Recorder:
    """Nimmt zwischen start() und stop() auf. Das Mikrofon ist nur währenddessen offen."""

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        if self._stream is not None:
            return
        self._chunks = []
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=self._on_audio,
            )
            self._stream.start()
        except (sd.PortAudioError, ValueError) as exc:
            self._stream = None
            raise RecorderError(
                "Kein Mikrofon verfügbar. Ist eins angeschlossen und in den "
                "Windows-Datenschutzeinstellungen für Desktop-Apps freigegeben?"
            ) from exc

    def stop(self) -> np.ndarray:
        """Beendet die Aufnahme und gibt das Audio als 1-D-Array zurück."""
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        self._stream.stop()
        self._stream.close()
        self._stream = None
        with self._lock:
            chunks, self._chunks = self._chunks, []
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks)

    def _on_audio(self, indata: np.ndarray, frames: int, time: object, status: object) -> None:
        # Läuft im Audio-Thread: nur kopieren, nichts Langsames tun.
        with self._lock:
            self._chunks.append(indata[:, 0].copy())
