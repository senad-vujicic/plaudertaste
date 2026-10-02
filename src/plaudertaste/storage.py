"""Absturzsicheres Speichern für alle eigenen Dateien (Einstellungen, Wörterbuch, Statistik).

Erst in eine Zwischendatei schreiben, dann in einem Schritt ersetzen: Ein Absturz oder
Stromausfall mitten im Speichern hinterlässt so nie eine halbe, unlesbare Datei.
"""

from __future__ import annotations

import os
from pathlib import Path


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)
