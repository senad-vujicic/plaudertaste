import logging

import numpy as np
import pytest

from plaudertaste.app import App
from plaudertaste.recorder import RecorderError

RATE = 16_000


class FakeRecorder:
    sample_rate = RATE

    def __init__(self, seconds: float = 1.0, fail_on_start: bool = False) -> None:
        self.audio = np.zeros(int(seconds * RATE), dtype=np.float32)
        self.fail_on_start = fail_on_start
        self.stopped = 0

    def start(self) -> None:
        if self.fail_on_start:
            raise RecorderError("Kein Mikrofon verfügbar.")

    def stop(self) -> np.ndarray:
        self.stopped += 1
        return self.audio


class FakeTranscriber:
    def __init__(self, results: list[str | Exception]) -> None:
        self.results = results

    def transcribe(self, audio: np.ndarray) -> str:
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def run_dictations(app: App, count: int) -> None:
    """Simuliert `count` Mal Taste halten + loslassen und wartet, bis alles verarbeitet ist."""
    app.start()
    for _ in range(count):
        app.on_start()
        app.on_stop()
    app.stop()


def test_dictation_is_transcribed_and_pasted() -> None:
    pasted: list[str] = []
    app = App(FakeTranscriber(["Hallo Welt"]), FakeRecorder(), paste=pasted.append)  # type: ignore[arg-type]

    run_dictations(app, 1)

    assert pasted == ["Hallo Welt "]


def test_consecutive_dictations_are_separated_by_a_space() -> None:
    pasted: list[str] = []
    app = App(FakeTranscriber(["Hey, was geht?", "Alles gut."]), FakeRecorder(), paste=pasted.append)  # type: ignore[arg-type]

    run_dictations(app, 2)

    assert "".join(pasted) == "Hey, was geht? Alles gut. "


def test_too_short_recording_is_ignored() -> None:
    pasted: list[str] = []
    transcriber = FakeTranscriber(["sollte nie kommen"])
    app = App(transcriber, FakeRecorder(seconds=0.1), paste=pasted.append)  # type: ignore[arg-type]

    run_dictations(app, 1)

    assert pasted == []
    assert transcriber.results == ["sollte nie kommen"]  # gar nicht erst transkribiert


def test_empty_text_is_not_pasted() -> None:
    pasted: list[str] = []
    app = App(FakeTranscriber([""]), FakeRecorder(), paste=pasted.append)  # type: ignore[arg-type]

    run_dictations(app, 1)

    assert pasted == []


def test_error_in_one_dictation_does_not_stop_the_next() -> None:
    pasted: list[str] = []
    transcriber = FakeTranscriber([RuntimeError("kaputt"), "zweiter Versuch"])
    app = App(transcriber, FakeRecorder(), paste=pasted.append)  # type: ignore[arg-type]

    run_dictations(app, 2)

    assert pasted == ["zweiter Versuch "]


def test_cancel_discards_recording() -> None:
    pasted: list[str] = []
    recorder = FakeRecorder()
    app = App(FakeTranscriber([]), recorder, paste=pasted.append)  # type: ignore[arg-type]

    app.start()
    app.on_start()
    app.on_cancel()
    app.stop()

    assert recorder.stopped == 1
    assert pasted == []


def test_missing_microphone_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    app = App(FakeTranscriber([]), FakeRecorder(fail_on_start=True))  # type: ignore[arg-type]

    with caplog.at_level(logging.ERROR):
        app.on_start()

    assert "Kein Mikrofon" in caplog.text
