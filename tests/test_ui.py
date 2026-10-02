import pytest

from plaudertaste.main_window import StartPage
from plaudertaste.ui import KeyCaps, ToggleSwitch, count_text, format_duration


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(0, "0 s"), (44.6, "45 s"), (60, "1 min"), (3599, "59 min"), (3900, "1 h 05 min")],
)
def test_format_duration(seconds: float, text: str) -> None:
    assert format_duration(seconds) == text


@pytest.mark.parametrize(
    ("count", "text"), [(0, "0 Wörter"), (1, "1 Wort"), (2, "2 Wörter"), (1234, "1.234 Wörter")]
)
def test_count_text(count: int, text: str) -> None:
    assert count_text(count, "Wort", "Wörter") == text


@pytest.mark.usefixtures("qapp")
def test_toggle_switch_behaves_like_checkbox() -> None:
    switch = ToggleSwitch("Ton")
    switch.resize(switch.sizeHint())
    toggled: list[bool] = []
    switch.toggled.connect(toggled.append)

    switch.click()
    switch.click()

    assert toggled == [True, False]
    assert switch.sizeHint().width() > 38  # Schalter + Text


@pytest.mark.usefixtures("qapp")
def test_keycaps_grow_with_each_key() -> None:
    single, combo = KeyCaps(), KeyCaps()
    single.set_keys("F9")
    combo.set_keys("Strg + Alt + F12")

    assert combo.keys() == ["Strg", "Alt", "F12"]
    assert combo.sizeHint().width() > 2 * single.sizeHint().width()
    assert not combo.grab().isNull()


@pytest.mark.usefixtures("qapp")
def test_start_page_shows_hotkey_as_keys() -> None:
    page = StartPage(lambda text: None)

    page.set_info("Strg + Leertaste", "small · Prozessor", "Deutsch", "Windows-Standard")

    assert page.keycaps.keys() == ["Strg", "Leertaste"]
    assert "Strg + Leertaste" in page.instructions.text()
