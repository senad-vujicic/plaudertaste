import ctypes
from collections.abc import Iterator

import pytest

from plaudertaste.clipboard import WindowsClipboard
from plaudertaste.paster import paste_text


class FakeClipboard:
    def __init__(self, content: str) -> None:
        self.content = content
        self.history: list[str] = []

    def copy(self, text: str) -> None:
        self.content = text
        self.history.append(text)

    def paste(self) -> str:
        return self.content


def run(clipboard: FakeClipboard, text: str) -> list[str]:
    """Führt paste_text aus und merkt sich, was beim Strg+V in der Zwischenablage lag."""
    pasted: list[str] = []
    paste_text(
        text,
        clipboard=clipboard,
        send_paste=lambda: pasted.append(clipboard.content),
        settle_delay=0,
        restore_delay=0,
    )
    return pasted


def test_pastes_text_and_restores_previous_clipboard() -> None:
    clipboard = FakeClipboard("alter Inhalt")

    pasted = run(clipboard, "Hallo Welt")

    assert pasted == ["Hallo Welt"]
    assert clipboard.content == "alter Inhalt"


def test_keeps_dictated_text_when_clipboard_was_empty() -> None:
    clipboard = FakeClipboard("")

    pasted = run(clipboard, "Hallo Welt")

    assert pasted == ["Hallo Welt"]
    assert clipboard.content == "Hallo Welt"
    assert clipboard.history == ["Hallo Welt"]


def test_line_breaks_use_windows_format() -> None:
    clipboard = FakeClipboard("")

    pasted = run(clipboard, "Einkaufsliste:\nMilch\r\nBrot\n\n")

    assert pasted == ["Einkaufsliste:\r\nMilch\r\nBrot\r\n\r\n"]  # nie doppelt \r\r\n


# --- echte Windows-Zwischenablage ---


@pytest.fixture
def real_clipboard() -> Iterator[WindowsClipboard]:
    """Die echte Zwischenablage – der vorherige Text wird danach zurückgelegt."""
    clipboard = WindowsClipboard()
    before = clipboard.paste()
    yield clipboard
    clipboard.copy(before)


def _clipboard_bytes(name: str) -> bytes | None:
    from plaudertaste import clipboard as cb

    with cb._opened():
        clipboard_format = cb._user32.RegisterClipboardFormatW(name)
        if not cb._user32.IsClipboardFormatAvailable(clipboard_format):
            return None
        handle = cb._user32.GetClipboardData(clipboard_format)
        pointer = cb._kernel32.GlobalLock(handle)
        try:
            return ctypes.string_at(pointer, cb._kernel32.GlobalSize(handle))
        finally:
            cb._kernel32.GlobalUnlock(handle)


def test_real_clipboard_round_trip(real_clipboard: WindowsClipboard) -> None:
    text = "Grüße aus Ingolstadt – 100 % lokal ✓\r\nZweite Zeile"

    real_clipboard.copy(text)

    assert real_clipboard.paste() == text


def test_dictated_text_is_kept_out_of_history_and_cloud(real_clipboard: WindowsClipboard) -> None:
    real_clipboard.copy("vertraulich")

    assert _clipboard_bytes("ExcludeClipboardContentFromMonitorProcessing") is not None
    history = _clipboard_bytes("CanIncludeInClipboardHistory")
    cloud = _clipboard_bytes("CanUploadToCloudClipboard")
    assert history is not None and int.from_bytes(history[:4], "little") == 0
    assert cloud is not None and int.from_bytes(cloud[:4], "little") == 0
