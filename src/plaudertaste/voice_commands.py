"""Sprachbefehle: "neue Zeile", "neuer Absatz", "Komma", "Fragezeichen" … werden zu Zeichen.

Bewusst NICHT dabei: "Punkt" – das ist zu oft ein normales Wort ("Der wichtigste Punkt ist …"),
und den Punkt am Satzende setzt Whisper ohnehin zuverlässig selbst.

Whisper setzt um Befehlswörter oft eigene Satzzeichen ("Komma," / "Neuer Absatz, ich").
Diese Zeichen direkt am Befehl fallen weg, damit kein doppeltes Zeichen entsteht.
"""

from __future__ import annotations

import re

_PUNCTUATION = {
    "komma": ",",
    "fragezeichen": "?",
    "ausrufezeichen": "!",
    "doppelpunkt": ":",
}
# "neuer/neue/neuen": Whisper beugt die Wörter nicht immer richtig ("neue Absatz").
_LINE_BREAKS = (
    (r"neue[rn]?\s+absatz", "\n\n"),
    (r"neue[rn]?\s+zeile", "\n"),
)


def apply_voice_commands(text: str) -> str:
    for word, symbol in _PUNCTUATION.items():
        # Leerzeichen und Whisper-Komma davor sowie Whisper-Zeichen direkt danach fallen weg.
        text = re.sub(rf"\s*[,;]?\s*\b{word}\b[,.;:]?", symbol, text, flags=re.IGNORECASE)
    for pattern, line_break in _LINE_BREAKS:
        text = re.sub(
            rf"[ \t]*[,;]?[ \t]*\b{pattern}\b[,.;:]?[ \t]*", line_break, text, flags=re.IGNORECASE
        )
    # Nach einem Umbruch oder einem diktierten ?/! beginnt ein neuer Satz.
    return re.sub(r"(\n|[?!] )(\w)", lambda m: m.group(1) + m.group(2).upper(), text)
