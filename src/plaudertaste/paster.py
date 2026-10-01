"""Text an der Cursorposition einfügen – über die Zwischenablage und Strg+V."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

import pyperclip
from pynput.keyboard import Controller, Key


class Clipboard(Protocol):
    def copy(self, text: str) -> None: ...
    def paste(self) -> str: ...


def press_ctrl_v() -> None:
    keyboard = Controller()
    with keyboard.pressed(Key.ctrl):
        keyboard.tap("v")


def paste_text(
    text: str,
    clipboard: Clipboard = pyperclip,
    send_paste: Callable[[], None] = press_ctrl_v,
    settle_delay: float = 0.05,
    restore_delay: float = 0.3,
) -> None:
    """Fügt `text` ein und stellt danach die vorherige Zwischenablage wieder her.

    War vorher kein Text in der Zwischenablage (leer oder z. B. ein Bild),
    bleibt der diktierte Text darin – als Backup zum erneuten Einfügen.
    """
    previous = clipboard.paste()
    clipboard.copy(text)
    time.sleep(settle_delay)  # Windows braucht einen Moment, bis die Zwischenablage gesetzt ist
    send_paste()
    if previous:
        time.sleep(restore_delay)  # Zielprogramm muss erst einfügen, bevor wir zurücksetzen
        clipboard.copy(previous)
