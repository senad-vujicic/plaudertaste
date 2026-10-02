"""Statistik über Diktate – gespeichert werden nur Zahlen pro Tag, nie Text."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from plaudertaste.storage import write_text_atomic

log = logging.getLogger(__name__)

TYPING_WPM = 40  # Annahme fürs Tippen (gängiger Durchschnitt), wird im Fenster angezeigt


def count_words(text: str) -> int:
    return len(text.split())


@dataclass(frozen=True)
class Totals:
    words: int = 0
    dictations: int = 0
    seconds: float = 0.0  # Sprechdauer

    def __add__(self, other: Totals) -> Totals:
        return Totals(
            self.words + other.words,
            self.dictations + other.dictations,
            self.seconds + other.seconds,
        )

    @property
    def saved_seconds(self) -> float:
        """Geschätzte gesparte Zeit: Tippzeit für die Wörter minus Sprechzeit."""
        return max(0.0, self.words / TYPING_WPM * 60 - self.seconds)


class Stats:
    def __init__(self, path: Path, today: Callable[[], date] = date.today) -> None:
        self._path = path
        self._today = today
        self._days: dict[date, Totals] = self._load()

    def record(self, text: str, seconds: float) -> None:
        day = self._today()
        self._days[day] = self._days.get(day, Totals()) + Totals(count_words(text), 1, seconds)
        self._save()

    def today(self) -> Totals:
        return self._days.get(self._today(), Totals())

    def this_week(self) -> Totals:
        """Montag bis heute."""
        today = self._today()
        monday = today - timedelta(days=today.weekday())
        return sum((t for d, t in self._days.items() if monday <= d <= today), Totals())

    def total(self) -> Totals:
        return sum(self._days.values(), Totals())

    def daily(self, days: int) -> list[tuple[date, Totals]]:
        """Die letzten `days` Tage bis heute, älteste zuerst – Tage ohne Diktat mit 0."""
        today = self._today()
        return [
            (day, self._days.get(day, Totals()))
            for day in (today - timedelta(days=offset) for offset in range(days - 1, -1, -1))
        ]

    def reset(self) -> None:
        self._days = {}
        self._save()

    def _load(self) -> dict[date, Totals]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return {
                date.fromisoformat(day): Totals(**values) for day, values in raw["days"].items()
            }
        except (ValueError, KeyError, TypeError) as exc:
            # Kaputte Datei aufheben statt still zu überschreiben – und neu anfangen.
            backup = self._path.with_suffix(".defekt.json")
            os.replace(self._path, backup)
            log.warning("Statistik-Datei defekt (%s) – gesichert als %s, starte neu.", exc, backup)
            return {}

    def _save(self) -> None:
        data = {"days": {day.isoformat(): asdict(t) for day, t in sorted(self._days.items())}}
        write_text_atomic(self._path, json.dumps(data, indent=2))
