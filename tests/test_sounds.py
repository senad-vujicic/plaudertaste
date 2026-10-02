import numpy as np
import pytest
import sounddevice as sd

from plaudertaste.app import Status
from plaudertaste.sounds import (
    START_TONE,
    STOP_TONE,
    TonePlayer,
    make_tone,
    play_blocking,
    tone_for_transition,
)


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


def test_missing_speaker_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_device(**kwargs: object) -> None:
        raise sd.PortAudioError("Kein Ausgabegerät")

    monkeypatch.setattr(sd, "RawOutputStream", no_device)

    play_blocking(START_TONE)  # nur Warnung im Log, keine Ausnahme


def test_tone_is_written_as_raw_float32_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    written: list[bytes] = []

    class FakeStream:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs == {"samplerate": 44_100, "channels": 1, "dtype": "float32"}

        def __enter__(self) -> "FakeStream":
            return self

        def __exit__(self, *args: object) -> None: ...

        def write(self, data: bytes) -> None:
            written.append(data)

    monkeypatch.setattr(sd, "RawOutputStream", FakeStream)

    play_blocking(STOP_TONE)

    assert written == [STOP_TONE.tobytes()]
