import logging
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from plaudertaste.logging_setup import setup_logging


@pytest.fixture(autouse=True)
def restore_logging(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """setup_logging verändert globalen Zustand – nach jedem Test zurücksetzen."""
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    yield
    root = logging.getLogger()
    for handler in root.handlers[:]:
        handler.close()
        root.removeHandler(handler)


def test_messages_are_written_to_log_file(tmp_path: Path) -> None:
    log_file = setup_logging(tmp_path / "logs", console=False)

    logging.getLogger("plaudertaste.test").info("Hallo Logdatei")

    assert log_file.parent == tmp_path / "logs"
    assert "Hallo Logdatei" in log_file.read_text(encoding="utf-8")


def test_noisy_libraries_are_quiet(tmp_path: Path) -> None:
    log_file = setup_logging(tmp_path, console=False)

    logging.getLogger("httpx").info("GET https://huggingface.co/...")

    assert "huggingface" not in log_file.read_text(encoding="utf-8")


def test_crash_in_thread_is_logged(tmp_path: Path) -> None:
    log_file = setup_logging(tmp_path, console=False)

    def crash() -> None:
        raise RuntimeError("Absturz im Hintergrund")

    thread = threading.Thread(target=crash, name="worker")
    thread.start()
    thread.join()

    text = log_file.read_text(encoding="utf-8")
    assert "Unerwarteter Fehler im Thread worker" in text
    assert "RuntimeError: Absturz im Hintergrund" in text
