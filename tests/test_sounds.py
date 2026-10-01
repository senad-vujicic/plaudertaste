import numpy as np
import pytest
import sounddevice as sd

from plaudertaste.app import Status
from plaudertaste.sounds import START_TONE, STOP_TONE, TonePlayer, make_tone, tone_for_transition


def test_tone_is_short_quiet_and_starts_and_ends_silent() -> None:
    tone = make_tone(600, 900, duration_s=0.07, volume=0.2)

    assert tone.dtype == np.float32
    assert tone.size == int(44_100 * 0.07)
    assert np.abs(tone).max() <= 0.2
    assert abs(tone[0]) < 1e-3 and abs(tone[-1]) < 1e-3  # kein Knacken


@pytest.mark.parametrize(
    ("previous", "current", "expected"),
    [
        (Status.READY, Status.RECORDING, START_TONE),
        (Status.PROCESSING, Status.RECORDING, START_TONE),
        (Status.RECORDING, Status.PROCESSING, STOP_TONE),
        (Status.RECORDING, Status.READY, STOP_TONE),  # zu kurz oder abgebrochen
        (Status.PROCESSING, Status.READY, None),
        (Status.LOADING, Status.READY, None),
        (Status.RECORDING, Status.RECORDING, None),
    ],
)
def test_tone_for_transition(
    previous: Status, current: Status, expected: np.ndarray | None
) -> None:
    assert tone_for_transition(previous, current) is expected


def test_disabled_player_plays_nothing() -> None:
    played: list[np.ndarray] = []
    player = TonePlayer(enabled=False, play=played.append)

    player.play(START_TONE)
    player.enabled = True
    player.play(STOP_TONE)

    assert played == [STOP_TONE]


def test_audio_error_does_not_raise() -> None:
    def broken(tone: np.ndarray) -> None:
        raise sd.PortAudioError("Kein Ausgabegerät")

    TonePlayer(enabled=True, play=broken).play(START_TONE)
