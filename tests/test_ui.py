import pytest

from plaudertaste.ui import count_text, format_duration


@pytest.mark.parametrize(
    ("seconds", "text"), [(0, "0 s"), (44.6, "45 s"), (60, "1 min"), (3599, "59 min"), (3900, "1 h 05 min")]
)
def test_format_duration(seconds: float, text: str) -> None:
    assert format_duration(seconds) == text


@pytest.mark.parametrize(
    ("count", "text"), [(0, "0 Wörter"), (1, "1 Wort"), (2, "2 Wörter"), (1234, "1.234 Wörter")]
)
def test_count_text(count: int, text: str) -> None:
    assert count_text(count, "Wort", "Wörter") == text
