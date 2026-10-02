import pytest
from pynput.keyboard import Key, KeyCode

from plaudertaste.hotkey import (
    HotkeyCapture,
    PushToTalk,
    describe_hotkey,
    hotkey_problem,
    key_name,
    parse_hotkey,
)


class Clock:
    """Steuerbare Uhr. Ohne Zutun vergeht pro Abfrage 1 s – jeder Tastendruck wirkt dann
    "lange gehalten", also kein Doppeltippen."""

    def __init__(self, step: float = 1.0) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


class Recorder:
    """Merkt sich, welche Callbacks der Automat in welcher Reihenfolge aufruft."""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.clock = Clock()

    def make(self, combo: str) -> PushToTalk:
        return PushToTalk(
            parse_hotkey(combo),
            on_start=lambda: self.events.append("start"),
            on_stop=lambda: self.events.append("stop"),
            on_cancel=lambda: self.events.append("cancel"),
            on_hands_free=lambda: self.events.append("hands_free"),
            on_undo=lambda: self.events.append("undo"),
            clock=self.clock,
        )


@pytest.fixture
def log() -> Recorder:
    return Recorder()


def test_hold_and_release_single_key(log: Recorder) -> None:
    ptt = log.make("ctrl_r")

    ptt.press("ctrl_r")
    assert ptt.is_recording
    ptt.release("ctrl_r")

    assert log.events == ["start", "stop"]
    assert not ptt.is_recording


def test_key_repeat_does_not_restart(log: Recorder) -> None:
    ptt = log.make("ctrl_r")

    for _ in range(5):
        ptt.press("ctrl_r")
    ptt.release("ctrl_r")

    assert log.events == ["start", "stop"]


def test_other_key_during_recording_cancels(log: Recorder) -> None:
    ptt = log.make("ctrl_r")

    ptt.press("ctrl_r")
    ptt.press("c")  # Strg+C
    ptt.release("c")
    ptt.release("ctrl_r")

    assert log.events == ["start", "cancel"]


def test_works_again_after_cancel(log: Recorder) -> None:
    ptt = log.make("ctrl_r")
    ptt.press("ctrl_r")
    ptt.press("c")
    ptt.release("c")
    ptt.release("ctrl_r")

    ptt.press("ctrl_r")
    ptt.release("ctrl_r")

    assert log.events == ["start", "cancel", "start", "stop"]


def test_does_not_start_when_other_key_already_held(log: Recorder) -> None:
    ptt = log.make("ctrl_r")

    ptt.press("shift_l")
    ptt.press("ctrl_r")  # Strg+Umschalt-Kürzel, kein Diktat
    ptt.release("ctrl_r")
    ptt.release("shift_l")

    assert log.events == []


def test_wrong_side_does_not_trigger(log: Recorder) -> None:
    ptt = log.make("ctrl_r")

    ptt.press("ctrl_l")
    ptt.release("ctrl_l")

    assert log.events == []


def test_combo_starts_only_when_all_keys_held(log: Recorder) -> None:
    ptt = log.make("ctrl+cmd")

    ptt.press("ctrl_l")
    assert log.events == []
    ptt.press("cmd")
    assert log.events == ["start"]
    ptt.release("ctrl_l")  # eine Taste der Kombination loslassen beendet
    ptt.release("cmd")

    assert log.events == ["start", "stop"]


def test_generic_modifier_matches_both_sides(log: Recorder) -> None:
    ptt = log.make("ctrl")

    ptt.press("ctrl_r")
    ptt.release("ctrl_r")
    ptt.press("ctrl_l")
    ptt.release("ctrl_l")

    assert log.events == ["start", "stop", "start", "stop"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ctrl_r", {"ctrl_r"}),
        ("CTRL + Cmd", {"ctrl", "cmd"}),
        ("f9", {"f9"}),
        ("ctrl+space", {"ctrl", "space"}),
        ("alt+d", {"alt", "d"}),
    ],
)
def test_parse_hotkey(text: str, expected: set[str]) -> None:
    assert parse_hotkey(text) == expected


@pytest.mark.parametrize("text", ["", "ctrl+", "strg", "ctrl+hyper"])
def test_parse_hotkey_rejects_invalid(text: str) -> None:
    with pytest.raises(ValueError):
        parse_hotkey(text)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (Key.ctrl_r, "ctrl_r"),
        (Key.f9, "f9"),
        (KeyCode(vk=0x43, char="\x03"), "c"),  # 'C' bei gehaltener Strg-Taste
        (KeyCode(vk=0x31, char="1"), "1"),
        (KeyCode(char="ß"), "ß"),
        (KeyCode(vk=173), "vk173"),
        (None, None),
    ],
)
def test_key_name(key: Key | KeyCode | None, expected: str | None) -> None:
    assert key_name(key) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ctrl_r", "Rechte Strg"),
        ("ctrl+cmd", "Strg + Win"),
        ("f9", "F9"),
        ("alt+d", "Alt + D"),
    ],
)
def test_describe_hotkey(text: str, expected: str) -> None:
    assert describe_hotkey(text) == expected


def test_capture_single_key() -> None:
    captured: list[str] = []
    capture = HotkeyCapture(captured.append)

    capture.press("f9")
    capture.press("f9")  # Tastenwiederholung
    capture.release("f9")

    assert captured == ["f9"]


def test_capture_combination_finishes_when_all_keys_released() -> None:
    captured: list[str] = []
    capture = HotkeyCapture(captured.append)

    capture.press("ctrl_l")
    capture.press("cmd")
    capture.release("cmd")
    assert captured == []  # Strg wird noch gehalten
    capture.release("ctrl_l")

    assert captured == ["ctrl_l+cmd"]


@pytest.mark.parametrize("text", ["ctrl_r", "f9", "ctrl_l+space", "alt+d", "ctrl+cmd"])
def test_good_hotkeys_have_no_problem(text: str) -> None:
    assert hotkey_problem(text) is None


@pytest.mark.parametrize(
    ("text", "hint"),
    [
        ("a", "beim Schreiben gebraucht"),
        ("space", "beim Schreiben gebraucht"),
        ("shift_l", "beim Schreiben gebraucht"),
        ("vk173", "nicht unterstützt"),
    ],
)
def test_bad_hotkeys_are_explained(text: str, hint: str) -> None:
    problem = hotkey_problem(text)

    assert problem is not None and hint in problem



# --- Doppeltippen (Freihand) ---


def tap(ptt: PushToTalk, clock: Clock, hold: float = 0.1, gap: float = 0.0) -> None:
    clock.now += gap
    clock.step = 0
    ptt.press("ctrl_r")
    clock.now += hold
    ptt.release("ctrl_r")


def test_double_tap_starts_hands_free_and_tap_stops_it(log: Recorder) -> None:
    ptt = log.make("ctrl_r")

    tap(ptt, log.clock)
    tap(ptt, log.clock, gap=0.2)
    assert ptt.is_hands_free
    assert log.events == ["start", "stop", "start", "hands_free"]

    tap(ptt, log.clock, gap=30)  # später: einmal tippen beendet
    assert not ptt.is_recording
    assert log.events[-1] == "stop"


def test_two_slow_taps_are_no_double_tap(log: Recorder) -> None:
    ptt = log.make("ctrl_r")

    tap(ptt, log.clock)
    tap(ptt, log.clock, gap=1.0)  # Pause zu lang

    assert not ptt.is_hands_free
    assert log.events == ["start", "stop", "start", "stop"]


def test_long_hold_after_tap_is_normal_dictation(log: Recorder) -> None:
    ptt = log.make("ctrl_r")

    tap(ptt, log.clock)
    tap(ptt, log.clock, hold=3.0, gap=0.2)  # zweites Mal gehalten = normales Diktat

    assert not ptt.is_hands_free
    assert log.events == ["start", "stop", "start", "stop"]


def test_typing_during_hands_free_is_ignored(log: Recorder) -> None:
    ptt = log.make("ctrl_r")
    tap(ptt, log.clock)
    tap(ptt, log.clock, gap=0.2)

    ptt.press("a")
    ptt.release("a")

    assert ptt.is_hands_free
    assert "cancel" not in log.events


def test_hands_free_can_be_stopped_from_outside(log: Recorder) -> None:
    ptt = log.make("ctrl_r")
    tap(ptt, log.clock)
    tap(ptt, log.clock, gap=0.2)

    ptt.stop_hands_free()
    ptt.stop_hands_free()  # zweimal ist harmlos

    assert log.events.count("stop") == 2  # erstes Tippen + Notstopp
    assert not ptt.is_recording


# --- Rückgängig: Hotkey halten + Rücktaste ---


def test_backspace_while_holding_requests_undo_after_release(log: Recorder) -> None:
    ptt = log.make("ctrl_r")

    ptt.press("ctrl_r")
    assert ptt.wants_to_swallow("backspace")
    ptt.press("backspace")
    ptt.release("backspace")
    assert log.events == ["start", "cancel"]  # noch kein undo – Strg ist noch gehalten

    ptt.release("ctrl_r")

    assert log.events == ["start", "cancel", "undo"]
    assert not ptt.wants_to_swallow("backspace")


def test_other_shortcut_does_not_undo(log: Recorder) -> None:
    ptt = log.make("ctrl_r")

    ptt.press("ctrl_r")
    assert not ptt.wants_to_swallow("c")
    ptt.press("c")
    ptt.release("c")
    ptt.release("ctrl_r")

    assert log.events == ["start", "cancel"]
