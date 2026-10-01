"""Kurze Signaltöne bei Start und Ende der Aufnahme – im Code erzeugt, ohne Sounddateien."""

from __future__ import annotations

import logging
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


def _play_with_sounddevice(tone: np.ndarray) -> None:
    sd.play(tone, SAMPLE_RATE)  # kehrt sofort zurück, spielt im Hintergrund


class TonePlayer:
    def __init__(
        self, enabled: bool, play: Callable[[np.ndarray], None] = _play_with_sounddevice
    ) -> None:
        self.enabled = enabled
        self._play = play

    def play(self, tone: np.ndarray) -> None:
        if not self.enabled:
            return
        try:
            self._play(tone)
        except sd.PortAudioError as exc:
            # Fehlender Lautsprecher darf das Diktieren nicht verhindern.
            log.warning("Ton konnte nicht abgespielt werden: %s", exc)
