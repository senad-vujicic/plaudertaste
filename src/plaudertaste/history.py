"""Verlauf der letzten Diktate – nur im Arbeitsspeicher, nach dem Beenden weg.

Datenschutz: Diktierter Text wird nie auf die Festplatte geschrieben.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

MAX_ENTRIES = 50


@dataclass(frozen=True)
class Entry:
    time: datetime
    text: str
    seconds: float


class History:
    def __init__(self, max_entries: int = MAX_ENTRIES) -> None:
        self._entries: deque[Entry] = deque(maxlen=max_entries)

    def add(self, text: str, seconds: float, time: datetime | None = None) -> Entry:
        entry = Entry(time or datetime.now(), text, seconds)
        self._entries.append(entry)
        return entry

    def entries(self) -> list[Entry]:
        """Neueste zuerst."""
        return list(reversed(self._entries))

    def clear(self) -> None:
        self._entries.clear()
