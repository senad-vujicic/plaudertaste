"""Kleine gemeinsame Bausteine für die Seiten des Hauptfensters."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel


def page_title(text: str) -> QLabel:
    label = QLabel(text)
    font = label.font()
    font.setPointSize(16)
    font.setBold(True)
    label.setFont(font)
    return label


def muted_label(text: str = "") -> QLabel:
    """Erklärender Text in gedämpfter Farbe, passt sich hellem und dunklem Design an."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setEnabled(False)  # nutzt die "deaktiviert"-Farbe des aktuellen Designs
    return label


def format_duration(seconds: float) -> str:
    """45 s, 3 min, 1 h 05 min."""
    seconds = round(seconds)
    if seconds < 60:
        return f"{seconds} s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d} min"


def count_text(count: int, singular: str, plural: str) -> str:
    """1 Wort, 2 Wörter – mit Tausenderpunkt (1.234 Wörter)."""
    number = f"{count:,}".replace(",", ".")
    return f"{number} {singular if count == 1 else plural}"
