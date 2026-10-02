"""Kurze Signaltöne bei Start und Ende der Aufnahme – im Code erzeugt, ohne Sounddateien.

Abgespielt über einen Roh-Stream (wie bei der Aufnahme, siehe recorder.py) in einem eigenen
Thread: Das Öffnen des Ausgabegeräts dauert ~100 ms und soll die Oberfläche nicht bremsen.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

import numpy as np
import sounddevice as sd

from plaudertaste.app import Status

log = logging.getLogger(__name__)

SAMPLE_RATE = 44_100


def make_tone(
    start_hz: float, end_hz: float, duration_s: float = 0.07, volume: float = 0.2
) -> np.ndarray:
    """Ein Ton, der von `start_hz` nach `end_hz` gleitet, mit weichem Ein- und Ausblenden."""
    samples = int(SAMPLE_RATE * duration_s)
    frequency = np.linspace(start_hz, end_hz, samples)
    phase = 2 * np.pi * np.cumsum(frequency) / SAMPLE_RATE
    tone = np.sin(phase) * volume

    fade = int(SAMPLE_RATE * 0.01)  # 10 ms – verhindert Knacken an den Rändern
    ramp = np.linspace(0.0, 1.0, fade)
    tone[:fade] *= ramp
    tone[-fade:] *= ramp[::-1]
    return tone.astype(np.float32)


START_TONE = make_tone(600, 900)  # steigend: "los geht's"
STOP_TONE = make_tone(900, 600)  # fallend: "fertig"


def tone_for_transition(previous: Status, current: Status) -> np.ndarray | None:
    """Welcher Ton passt zu einem Statuswechsel? None = kein Ton."""
    if current is Status.RECORDING and previous is not Status.RECORDING:
        return START_TONE
    if previous is Status.RECORDING and current is not Status.RECORDING:
        return STOP_TONE
    return None


def play_blocking(tone: np.ndarray) -> None:
    """Spielt den Ton und kehrt zurück, wenn er zu Ende ist."""
    try:
        with sd.RawOutputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as stream:
            stream.write(tone.tobytes())
    except sd.PortAudioError as exc:
        # Fehlender Lautsprecher darf das Diktieren nicht verhindern.
        log.warning("Ton konnte nicht abgespielt werden: %s", exc)


def play_in_background(tone: np.ndarray) -> None:
    threading.Thread(target=play_blocking, args=(tone,), name="tone", daemon=True).start()


class TonePlayer:
    def __init__(
        self, enabled: bool, play: Callable[[np.ndarray], None] = play_in_background
    ) -> None:
        self.enabled = enabled
        self._play = play

    def play(self, tone: np.ndarray) -> None:
        if self.enabled:
            self._play(tone)
