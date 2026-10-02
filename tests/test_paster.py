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
