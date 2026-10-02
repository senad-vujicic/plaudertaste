import pytest
from PySide6.QtCore import QCoreApplication

from plaudertaste import model_loader
from plaudertaste.config import Config
from plaudertaste.model_download import DownloadCancelled, DownloadFailed
from plaudertaste.model_loader import ModelLoader
from plaudertaste.network import OfflineError

pytestmark = pytest.mark.usefixtures("qapp")


def run_load(monkeypatch: pytest.MonkeyPatch, behaviour: object) -> list[tuple]:
    """Lässt den Loader mit einer Attrappe statt Whisper laufen und sammelt seine Signale."""

    class FakeTranscriber:
        def __init__(self, *args: object) -> None:
            if isinstance(behaviour, Exception):
                raise behaviour

    monkeypatch.setattr(model_loader, "Transcriber", FakeTranscriber)
    loader = ModelLoader()
    events: list[tuple] = []
    loader.loaded.connect(lambda t: events.append(("loaded",)))
    loader.failed.connect(lambda message, details: events.append(("failed", message, details)))
    loader.cancelled.connect(lambda: events.append(("cancelled",)))

    loader._run(Config(), loader._cancel)  # direkt im Test-Thread: deterministisch
    QCoreApplication.processEvents()
    return events


def test_successful_load(monkeypatch: pytest.MonkeyPatch) -> None:
    assert run_load(monkeypatch, None) == [("loaded",)]


def test_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    assert run_load(monkeypatch, DownloadCancelled()) == [("cancelled",)]


@pytest.mark.parametrize(
    ("error", "message_start"),
    [
        (DownloadFailed("ConnectError"), "Das Sprachmodell konnte nicht heruntergeladen"),
        (OfflineError("Offline-Modus: blockiert"), "Offline-Modus"),
        (RuntimeError("CUDA kaputt"), "Das Sprachmodell konnte nicht geladen werden"),
    ],
)
def test_errors_become_understandable_messages(
    monkeypatch: pytest.MonkeyPatch, error: Exception, message_start: str
) -> None:
    [(kind, message, details)] = run_load(monkeypatch, error)

    assert kind == "failed"
    assert message.startswith(message_start)
    assert details  # technische Details bleiben für die Fehlersuche erhalten


def test_each_load_gets_its_own_cancel_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        model_loader.threading,
        "Thread",
        lambda **kwargs: type("T", (), {"start": lambda self: None})(),
    )
    loader = ModelLoader()
    loader.cancel()
    assert loader.cancel_requested

    loader.load(Config())  # neuer Ladevorgang – der alte Abbruch gilt nicht mehr

    assert not loader.cancel_requested
