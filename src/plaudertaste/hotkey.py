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


def parse_hotkey(text: str) -> frozenset[str]:
    """Wandelt z. B. "ctrl+cmd" in {"ctrl", "cmd"} um und prüft die Tastennamen."""
    parts = [part.strip().lower() for part in text.split("+")]
    if not all(parts):
        raise ValueError(f"Ungültiger Hotkey '{text}'.")
    invalid = [part for part in parts if part not in _VALID_NAMES]
    if invalid:
        raise ValueError(f"Unbekannte Taste(n) im Hotkey: {', '.join(invalid)}")
    return frozenset(parts)


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


def start_listener(push_to_talk: PushToTalk) -> keyboard.Listener:
    """Startet den globalen Tastatur-Listener in einem eigenen Thread.

    Von Programmen simulierte Tastendrücke (z. B. unser eigenes Strg+V) werden ignoriert.
    """

    def on_press(key: keyboard.Key | keyboard.KeyCode | None, injected: bool) -> None:
        name = key_name(key)
        if name and not injected:
            push_to_talk.press(name)

    def on_release(key: keyboard.Key | keyboard.KeyCode | None, injected: bool) -> None:
        name = key_name(key)
        if name and not injected:
            push_to_talk.release(name)

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    return listener
