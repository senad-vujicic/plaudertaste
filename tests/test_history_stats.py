from datetime import date, datetime
from pathlib import Path

import pytest

from plaudertaste.history import History
from plaudertaste.stats import Stats, Totals, count_words


def test_history_newest_first_and_limited() -> None:
    history = History(max_entries=2)
    history.add("eins", 1.0, datetime(2026, 10, 2, 9, 0))
    history.add("zwei", 1.0, datetime(2026, 10, 2, 9, 1))
    history.add("drei", 1.0, datetime(2026, 10, 2, 9, 2))

    assert [e.text for e in history.entries()] == ["drei", "zwei"]
    history.clear()
    assert history.entries() == []


@pytest.mark.parametrize(("text", "words"), [("", 0), ("Hallo Welt", 2), ("  Hey,  was geht? ", 3)])
def test_count_words(text: str, words: int) -> None:
    assert count_words(text) == words


def test_saved_time_assumes_40_words_per_minute() -> None:
    # 80 Wörter tippen = 2 min = 120 s; gesprochen in 30 s -> 90 s gespart
    assert Totals(words=80, dictations=1, seconds=30).saved_seconds == 90
    assert Totals(words=1, dictations=1, seconds=10).saved_seconds == 0  # nie negativ


class Clock:
    def __init__(self, day: date) -> None:
        self.day = day

    def __call__(self) -> date:
        return self.day


def test_stats_today_week_total(tmp_path: Path) -> None:
    clock = Clock(date(2026, 9, 25))  # Freitag der Vorwoche
    stats = Stats(tmp_path / "stats.json", today=clock)
    stats.record("eins zwei", 1.0)
    clock.day = date(2026, 9, 28)  # Montag
    stats.record("drei vier fünf", 2.0)
    clock.day = date(2026, 10, 2)  # Freitag
    stats.record("sechs", 0.5)

    assert stats.today() == Totals(1, 1, 0.5)
    assert stats.this_week() == Totals(4, 2, 2.5)
    assert stats.total() == Totals(6, 3, 3.5)


def test_stats_survive_restart_and_contain_no_text(tmp_path: Path) -> None:
    path = tmp_path / "stats.json"
    Stats(path, today=Clock(date(2026, 10, 2))).record("geheimer Text", 1.5)

    reloaded = Stats(path, today=Clock(date(2026, 10, 2)))

    assert reloaded.today() == Totals(2, 1, 1.5)
    assert "geheim" not in path.read_text(encoding="utf-8")


def test_reset(tmp_path: Path) -> None:
    stats = Stats(tmp_path / "stats.json")
    stats.record("Hallo", 1.0)

    stats.reset()

    assert stats.total() == Totals()
    assert Stats(tmp_path / "stats.json").total() == Totals()


def test_broken_file_is_kept_and_stats_start_fresh(tmp_path: Path) -> None:
    path = tmp_path / "stats.json"
    path.write_text("{kaputt", encoding="utf-8")

    stats = Stats(path)

    assert stats.total() == Totals()
    assert (tmp_path / "stats.defekt.json").read_text(encoding="utf-8") == "{kaputt"
