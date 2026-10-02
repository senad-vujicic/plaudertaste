"""Push-to-Talk-Hotkey: Zustandsautomat plus Anbindung an die echte Tastatur (pynput)."""

from __future__ import annotations

import string
from collections.abc import Callable
from enum import Enum, auto

from pynput import keyboard

# Allgemeine Modifier-Namen passen auf die linke und die rechte Taste.
_GENERIC_KEYS: dict[str, frozenset[str]] = {
    "ctrl": frozenset({"ctrl", "ctrl_l", "ctrl_r"}),
    "alt": frozenset({"alt", "alt_l", "alt_r"}),
    "shift": frozenset({"shift", "shift_l", "shift_r"}),
    "cmd": frozenset({"cmd", "cmd_l", "cmd_r"}),
}
_VALID_NAMES = frozenset(keyboard.Key.__members__) | frozenset(
    string.ascii_lowercase + string.digits
)


# Tasten, die beim Schreiben gebraucht werden – allein als Hotkey würden sie ständig auslösen.
_TYPING_KEYS = frozenset(string.ascii_lowercase + string.digits) | frozenset(
    {"space", "enter", "backspace", "tab", "shift", "shift_l", "shift_r"}
)


def parse_hotkey(text: str) -> frozenset[str]:
    """Wandelt z. B. "ctrl+cmd" in {"ctrl", "cmd"} um und prüft die Tastennamen."""
    parts = [part.strip().lower() for part in text.split("+")]
    if not all(parts):
        raise ValueError(f"Ungültiger Hotkey '{text}'.")
    invalid = [part for part in parts if part not in _VALID_NAMES]
    if invalid:
        raise ValueError(f"Unbekannte Taste(n) im Hotkey: {', '.join(invalid)}")
    return frozenset(parts)


_DISPLAY_NAMES: dict[str, str] = {
    "ctrl": "Strg",
    "ctrl_l": "Linke Strg",
    "ctrl_r": "Rechte Strg",
    "shift": "Umschalt",
    "shift_l": "Linke Umschalt",
    "shift_r": "Rechte Umschalt",
    "alt": "Alt",
    "alt_l": "Alt",
    "alt_r": "Rechte Alt",
    "alt_gr": "AltGr",
    "cmd": "Win",
    "cmd_l": "Win",
    "cmd_r": "Rechte Win",
    "space": "Leertaste",
    "caps_lock": "Feststell",
    "scroll_lock": "Rollen",
    "pause": "Pause",
    "insert": "Einfg",
    "menu": "Menü",
}


def hotkey_problem(text: str) -> str | None:
    """Prüft einen Hotkey für die Einstellungen. None = in Ordnung, sonst ein Hinweistext."""
    try:
        combo = parse_hotkey(text)
    except ValueError:
        return "Diese Taste wird nicht unterstützt. Bitte eine andere wählen."
    if len(combo) == 1 and next(iter(combo)) in _TYPING_KEYS:
        return (
            "Diese Taste wird beim Schreiben gebraucht. Bitte eine andere wählen "
            "(z. B. rechte Strg oder eine F-Taste) oder sie mit Strg/Alt kombinieren."
        )
    return None


class HotkeyCapture:
    """Nimmt eine Tastenkombination auf: fertig, sobald alle Tasten losgelassen sind."""

    def __init__(self, on_done: Callable[[str], None]) -> None:
        self._on_done = on_done
        self._held: set[str] = set()
        self._combo: list[str] = []  # in Drück-Reihenfolge

    def press(self, key: str) -> None:
        self._held.add(key)
        if key not in self._combo:
            self._combo.append(key)

    def release(self, key: str) -> None:
        self._held.discard(key)
        if not self._held and self._combo:
            combo, self._combo = self._combo, []
            self._on_done("+".join(combo))


def describe_hotkey(text: str) -> str:
    """Lesbarer Name für die Oberfläche, z. B. "ctrl+cmd" -> "Strg + Win"."""
    parts = [part.strip().lower() for part in text.split("+")]
    return " + ".join(_DISPLAY_NAMES.get(part, part.upper()) for part in parts)


class _State(Enum):
    IDLE = auto()
    RECORDING = auto()
    CANCELLED = auto()


class PushToTalk:
    """Erkennt "Hotkey gehalten" und "Hotkey losgelassen".

    Wird während der Aufnahme eine fremde Taste gedrückt (z. B. Strg+C),
    gilt das als normales Tastenkürzel und die Aufnahme wird verworfen.
    """

    def __init__(
        self,
        combo: frozenset[str],
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        self._combo = combo
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_cancel = on_cancel
        self._pressed: set[str] = set()
        self._state = _State.IDLE

    @property
    def is_recording(self) -> bool:
        return self._state is _State.RECORDING

    def press(self, key: str) -> None:
        if key in self._pressed:  # Tastenwiederholung beim Gedrückthalten
            return
        self._pressed.add(key)

        if self._state is _State.IDLE and self._combo_held_exactly():
            self._state = _State.RECORDING
            self._on_start()
        elif self._state is _State.RECORDING and not self._is_combo_key(key):
            self._state = _State.CANCELLED
            self._on_cancel()

    def release(self, key: str) -> None:
        self._pressed.discard(key)

        if self._state is _State.RECORDING and self._is_combo_key(key):
            self._state = _State.IDLE
            self._on_stop()
        elif self._state is _State.CANCELLED and not any(
            self._is_combo_key(k) for k in self._pressed
        ):
            self._state = _State.IDLE

    def _is_combo_key(self, key: str) -> bool:
        return any(key in _GENERIC_KEYS.get(part, {part}) for part in self._combo)

    def _combo_held_exactly(self) -> bool:
        all_parts_held = all(
            self._pressed & _GENERIC_KEYS.get(part, {part}) for part in self._combo
        )
        no_extra_keys = all(self._is_combo_key(k) for k in self._pressed)
        return all_parts_held and no_extra_keys


def key_name(key: keyboard.Key | keyboard.KeyCode | None) -> str | None:
    """Einheitlicher Name für ein pynput-Tastenobjekt (z. B. "ctrl_r", "a", "vk173")."""
    if isinstance(key, keyboard.Key):
        return key.name
    if isinstance(key, keyboard.KeyCode):
        vk = key.vk
        # Buchstaben/Ziffern über den Tastencode, da 'char' bei gehaltener Strg-Taste
        # ein Steuerzeichen enthält (Strg+C -> '\x03').
        if vk is not None and (0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A):
            return chr(vk).lower()
        if key.char:
            return key.char.lower()
        if vk is not None:
            return f"vk{vk}"
    return None


def start_listener(
    on_press: Callable[[str], None], on_release: Callable[[str], None]
) -> keyboard.Listener:
    """Startet den globalen Tastatur-Listener in einem eigenen Thread.

    Die Callbacks bekommen Tastennamen (z. B. "ctrl_r") und laufen im Listener-Thread.
    Von Programmen simulierte Tastendrücke (z. B. unser eigenes Strg+V) werden ignoriert.
    """

    def handle_press(key: keyboard.Key | keyboard.KeyCode | None, injected: bool) -> None:
        name = key_name(key)
        if name and not injected:
            on_press(name)

    def handle_release(key: keyboard.Key | keyboard.KeyCode | None, injected: bool) -> None:
        name = key_name(key)
        if name and not injected:
            on_release(name)

    listener = keyboard.Listener(on_press=handle_press, on_release=handle_release)
    listener.start()
    return listener
