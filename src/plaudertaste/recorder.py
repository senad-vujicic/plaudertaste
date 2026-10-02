"""Mikrofon-Aufnahme im Format, das Whisper erwartet (16 kHz, mono, float32).

Wir nutzen den Roh-Stream von sounddevice und wandeln die Bytes selbst um: Die
NumPy-Umwandlung von sounddevice 0.5.6 nutzt eine Funktion, die NumPy 2.5 als veraltet
markiert hat – fällt sie weg, würde die Aufnahme sonst ausfallen.
"""

from __future__ import annotations

import logging
import threading

import numpy as np
import sounddevice as sd

from plaudertaste.devices import find_microphone

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000


class RecorderError(Exception):
    """Das Mikrofon konnte nicht geöffnet werden."""


class Recorder:
    """Nimmt zwischen start() und stop() auf. Das Mikrofon ist nur währenddessen offen."""

    def __init__(self, microphone: str = "", sample_rate: int = SAMPLE_RATE) -> None:
        self.microphone = microphone  # Gerätename, "" = Windows-Standard
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()  # schützt die Audio-Stücke (Audio-Thread)
        # Start/Stopp können aus dem Tastatur- und dem Haupt-Thread kommen (Modellwechsel)
        self._stream_lock = threading.Lock()
        self._stream: sd.RawInputStream | None = None
        self._level = 0.0
        # True, wenn das gewählte Mikrofon fehlte und der Windows-Standard genutzt wurde
        self.fell_back_to_default = False

    @property
    def level(self) -> float:
        """Aktuelle Lautstärke (RMS, 0–1) – für die Pegelanzeige."""
        return self._level

    def start(self) -> None:
        with self._stream_lock:
            self._start()

    def stop(self) -> np.ndarray:
        """Beendet die Aufnahme und gibt das Audio als 1-D-Array zurück."""
        with self._stream_lock:
            return self._stop()

    def _start(self) -> None:
        if self._stream is not None:
            return
        self._chunks = []
        self._level = 0.0
        device = find_microphone(self.microphone)
        self.fell_back_to_default = bool(self.microphone) and device is None
        if self.fell_back_to_default:
            log.warning("Mikrofon '%s' nicht gefunden – nutze Windows-Standard.", self.microphone)
        try:
            self._stream = sd.RawInputStream(
                device=device,
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

    def _stop(self) -> np.ndarray:
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        self._stream.stop()
        self._stream.close()
        self._stream = None
        self._level = 0.0
        with self._lock:
            chunks, self._chunks = self._chunks, []
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks)

    def _on_audio(self, indata: memoryview, frames: int, time: object, status: object) -> None:
        # Läuft im Audio-Thread: nur kopieren, nichts Langsames tun.
        # indata sind rohe Bytes (mono float32); copy(), weil der Puffer danach wiederverwendet wird.
        samples = np.frombuffer(indata, dtype=np.float32).copy()
        self._level = float(np.sqrt(np.mean(samples**2))) if samples.size else 0.0
        with self._lock:
            self._chunks.append(samples)
