import pytest
from pynput.keyboard import Key, KeyCode

from plaudertaste.hotkey import PushToTalk, describe_hotkey, key_name, parse_hotkey


class Recorder:
    """Merkt sich, welche Callbacks der Automat in welcher Reihenfolge aufruft."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def make(self, combo: str) -> PushToTalk:
        return PushToTalk(
            parse_hotkey(combo),
            on_start=lambda: self.events.append("start"),
            on_stop=lambda: self.events.append("stop"),
            on_cancel=lambda: self.events.append("cancel"),
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
