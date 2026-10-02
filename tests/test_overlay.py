import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from plaudertaste.app import Status
from plaudertaste.overlay import Overlay, format_elapsed, level_to_height


@pytest.mark.parametrize(
    ("rms", "expected"),
    [
        (0.0, 0.0),
        (0.001, 0.0),  # -60 dB: Stille
        (10 ** (-36 / 20), 0.5),  # -36 dB: halbe Höhe
        (10 ** (-12 / 20), 1.0),  # -12 dB: voll
        (1.0, 1.0),  # lauter wird abgeschnitten
    ],
)
def test_level_to_height_is_logarithmic(rms: float, expected: float) -> None:
    assert level_to_height(rms) == pytest.approx(expected)


@pytest.mark.parametrize(("seconds", "text"), [(0, "0:00"), (7.9, "0:07"), (65, "1:05")])
def test_format_elapsed(seconds: float, text: str) -> None:
    assert format_elapsed(seconds) == text


def test_overlay_is_shown_only_while_recording_or_processing(qapp: QApplication) -> None:
    overlay = Overlay(level_source=lambda: 0.1)

    overlay.set_status(Status.RECORDING)
    assert overlay.isVisible()
    overlay.set_status(Status.PROCESSING)
    assert overlay.isVisible()
    overlay.set_status(Status.READY)
    assert not overlay.isVisible()


def test_overlay_never_takes_focus_or_mouse(qapp: QApplication) -> None:
    flags = Overlay(level_source=lambda: 0.0).windowFlags()

    assert flags & Qt.WindowType.WindowDoesNotAcceptFocus
    assert flags & Qt.WindowType.WindowTransparentForInput
    assert flags & Qt.WindowType.WindowStaysOnTopHint


def test_levels_are_collected_while_recording(qapp: QApplication) -> None:
    overlay = Overlay(level_source=lambda: 0.5)  # -6 dB, lauter als 'voll'
    overlay.set_status(Status.RECORDING)

    overlay._tick()

    assert overlay._levels[-1] == pytest.approx(1.0)
    overlay.set_status(Status.READY)


def test_message_is_shown_and_survives_ready_status(qapp: QApplication) -> None:
    overlay = Overlay(level_source=lambda: 0.0)
    overlay.set_status(Status.PROCESSING)

    overlay.show_message("Nichts verstanden – bitte etwas länger oder deutlicher sprechen.")
    overlay.set_status(Status.READY)  # kommt direkt nach der Meldung – darf sie nicht verstecken

    assert overlay.isVisible()
    assert overlay.message is not None
    assert overlay.width() > 230  # passt sich dem Text an


def test_message_disappears_by_itself(qapp: QApplication) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    overlay = Overlay(level_source=lambda: 0.0)
    overlay._message_timer.setInterval(10)
    overlay.show_message("Kein Ton vom Mikrofon")

    loop = QEventLoop()
    QTimer.singleShot(150, loop.quit)
    loop.exec()

    assert not overlay.isVisible()
    assert overlay.width() == 230  # wieder normale Größe


def test_new_recording_replaces_message(qapp: QApplication) -> None:
    overlay = Overlay(level_source=lambda: 0.0)
    overlay.show_message("Kein Ton vom Mikrofon")

    overlay.set_status(Status.RECORDING)

    assert overlay.message is None
    assert overlay.status is Status.RECORDING
    overlay.set_status(Status.READY)
