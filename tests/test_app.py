import logging
import threading

import numpy as np
import pytest

from plaudertaste.app import (
    MIC_UNAVAILABLE,
    NOTHING_UNDERSTOOD,
    PASTE_FAILED,
    PROCESSING_FAILED,
    SILENT_MICROPHONE,
    App,
    Notice,
    Status,
)
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


def test_status_sequence_for_one_dictation() -> None:
    statuses: list[Status] = []
    app = App(FakeTranscriber(["Hallo"]), FakeRecorder(), paste=lambda text: None, on_status=statuses.append)  # type: ignore[arg-type]

    run_dictations(app, 1)

    assert statuses == [Status.READY, Status.RECORDING, Status.PROCESSING, Status.READY]


def test_status_stays_recording_while_previous_dictation_finishes() -> None:
    """Neue Aufnahme, während die vorige noch verarbeitet wird: Das Ende der vorigen
    darf den Status nicht auf READY zurücksetzen."""
    first_started = threading.Event()
    release_first = threading.Event()

    class SlowTranscriber:
        def transcribe(self, audio: np.ndarray) -> str:
            first_started.set()
            release_first.wait(timeout=5)
            return "erstes Diktat"

    statuses: list[Status] = []
    five_updates = threading.Event()

    def record_status(status: Status) -> None:
        statuses.append(status)
        if len(statuses) == 5:
            five_updates.set()

    app = App(SlowTranscriber(), FakeRecorder(), paste=lambda text: None, on_status=record_status)  # type: ignore[arg-type]
    app.start()
    app.on_start()
    app.on_stop()
    assert first_started.wait(timeout=5)

    app.on_start()  # zweite Aufnahme beginnt, während die erste noch läuft
    release_first.set()  # jetzt wird die erste fertig
    assert five_updates.wait(timeout=5)

    assert statuses == [
        Status.READY,
        Status.RECORDING,
        Status.PROCESSING,
        Status.RECORDING,  # zweite Aufnahme
        Status.RECORDING,  # erste fertig – Status bleibt korrekt auf Aufnahme
    ]
    app.on_cancel()
    app.stop()


def test_finished_dictation_is_reported_with_duration() -> None:
    reported: list[tuple[str, float]] = []
    app = App(
        FakeTranscriber(["Hallo", ""]),
        FakeRecorder(seconds=2.0),
        paste=lambda text: None,
        on_dictation=lambda text, seconds: reported.append((text, seconds)),
    )  # type: ignore[arg-type]

    run_dictations(app, 2)  # zweites Diktat ohne Text wird nicht gemeldet

    assert reported == [("Hallo", 2.0)]


class LoudRecorder(FakeRecorder):
    """Liefert hörbares Rauschen statt absoluter Stille."""

    def __init__(self) -> None:
        super().__init__()
        self.audio = np.full(RATE, 0.05, dtype=np.float32)


def run_with_notices(app_kwargs: dict, count: int = 1) -> list[Notice]:
    notices: list[Notice] = []
    app = App(on_notice=notices.append, **app_kwargs)
    run_dictations(app, count)
    return notices


def test_missing_microphone_is_reported() -> None:
    notices: list[Notice] = []
    app = App(FakeTranscriber([]), FakeRecorder(fail_on_start=True), on_notice=notices.append)  # type: ignore[arg-type]

    app.on_start()

    assert notices == [MIC_UNAVAILABLE]


def test_silence_points_to_muted_microphone() -> None:
    notices = run_with_notices(
        {"transcriber": FakeTranscriber([""]), "recorder": FakeRecorder(), "paste": lambda t: None}
    )

    assert notices == [SILENT_MICROPHONE]


def test_unclear_speech_is_reported_differently() -> None:
    notices = run_with_notices(
        {"transcriber": FakeTranscriber([""]), "recorder": LoudRecorder(), "paste": lambda t: None}
    )

    assert notices == [NOTHING_UNDERSTOOD]


def test_recognition_error_is_reported() -> None:
    notices = run_with_notices(
        {
            "transcriber": FakeTranscriber([RuntimeError("kaputt")]),
            "recorder": FakeRecorder(),
            "paste": lambda t: None,
        }
    )

    assert notices == [PROCESSING_FAILED]


def test_failed_paste_keeps_text_for_history() -> None:
    def broken_paste(text: str) -> None:
        raise RuntimeError("Zwischenablage blockiert")

    reported: list[tuple[str, float]] = []
    notices: list[Notice] = []
    app = App(
        FakeTranscriber(["Wichtiger Satz"]),
        FakeRecorder(),
        paste=broken_paste,
        on_dictation=lambda text, seconds: reported.append((text, seconds)),
        on_notice=notices.append,
    )  # type: ignore[arg-type]

    run_dictations(app, 1)

    assert notices == [PASTE_FAILED]
    assert reported == [("Wichtiger Satz", 1.0)]  # Text nicht verloren


def test_dictionary_replacements_and_hints_are_applied() -> None:
    from plaudertaste.dictionary import Dictionary, Replacement

    pasted: list[str] = []
    transcriber = FakeTranscriber(["Danke und mfg"])
    dictionary = Dictionary(
        terms=("Plaudertaste",), replacements=(Replacement("mfg", "Mit freundlichen Grüßen"),)
    )
    app = App(transcriber, FakeRecorder(), paste=pasted.append, dictionary=dictionary)  # type: ignore[arg-type]

    run_dictations(app, 1)

    assert pasted == ["Danke und Mit freundlichen Grüßen "]
    assert transcriber.hotwords == "Plaudertaste"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("enabled", "expected"),
    [
        (True, ["Einkaufsliste:\nMilch ", "Brot\n"]),  # nach Umbruch kein Leerzeichen
        (False, ["Einkaufsliste Doppelpunkt neue Zeile Milch ", "Brot neue Zeile "]),
    ],
)
def test_voice_commands_can_be_switched(enabled: bool, expected: list[str]) -> None:
    pasted: list[str] = []
    app = App(
        FakeTranscriber(["Einkaufsliste Doppelpunkt neue Zeile Milch", "Brot neue Zeile"]),
        FakeRecorder(),
        paste=pasted.append,
        voice_commands=enabled,
    )  # type: ignore[arg-type]

    run_dictations(app, 2)

    assert pasted == expected


@pytest.mark.parametrize(
    ("enabled", "expected"),
    [(True, ["Ich komme morgen. "]), (False, ["Ähm, ich komme äh morgen. "])],
)
def test_fillers_can_be_switched(enabled: bool, expected: list[str]) -> None:
    pasted: list[str] = []
    app = App(
        FakeTranscriber(["Ähm, ich komme äh morgen."]),
        FakeRecorder(),
        paste=pasted.append,
        remove_fillers=enabled,
    )  # type: ignore[arg-type]

    run_dictations(app, 1)

    assert pasted == expected


def test_processing_order_fillers_commands_dictionary() -> None:
    from plaudertaste.dictionary import Dictionary, Replacement

    pasted: list[str] = []
    app = App(
        FakeTranscriber(["Ähm, Gruß Komma mfg"]),
        FakeRecorder(),
        paste=pasted.append,
        dictionary=Dictionary(replacements=(Replacement("mfg", "Mit freundlichen Grüßen"),)),
    )  # type: ignore[arg-type]

    run_dictations(app, 1)

    assert pasted == ["Gruß, Mit freundlichen Grüßen "]


def test_dictation_of_only_fillers_pastes_nothing() -> None:
    pasted: list[str] = []
    reported: list[tuple[str, float]] = []
    app = App(
        FakeTranscriber(["Ähm."]),
        FakeRecorder(),
        paste=pasted.append,
        on_dictation=lambda text, seconds: reported.append((text, seconds)),
    )  # type: ignore[arg-type]

    run_dictations(app, 1)

    assert pasted == []
    assert reported == []  # kein leerer Eintrag im Verlauf


def test_undo_erases_exactly_the_last_dictation() -> None:
    from plaudertaste.app import UNDONE

    erased: list[int] = []
    notices: list[Notice] = []
    app = App(
        FakeTranscriber(["Erstes.", "Hallo Welt"]),
        FakeRecorder(),
        paste=lambda text: None,
        erase=erased.append,
        on_notice=notices.append,
    )  # type: ignore[arg-type]
    app.start()
    for _ in range(2):
        app.on_start()
        app.on_stop()
    app.on_undo()
    app.on_undo()  # zweites Mal: nichts mehr da
    app.stop()

    assert erased == [len("Hallo Welt ")]  # nur das letzte, inkl. Leerzeichen
    assert notices[0] is UNDONE
    assert notices[1].text.startswith("Nichts zum Rückgängigmachen")


def test_typing_after_dictation_blocks_undo() -> None:
    pasted = threading.Event()
    erased: list[int] = []
    app = App(
        FakeTranscriber(["Hallo"]),
        FakeRecorder(),
        paste=lambda text: pasted.set(),
        erase=erased.append,
    )  # type: ignore[arg-type]
    app.start()
    app.on_start()
    app.on_stop()
    assert pasted.wait(timeout=5)  # erst wenn wirklich eingefügt wurde …

    app.forget_last_dictation()  # … tippt der Nutzer selbst
    app.on_undo()
    app.stop()

    assert erased == []
