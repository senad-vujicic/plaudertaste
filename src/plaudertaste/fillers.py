"""Verzögerungslaute ("äh", "ähm", "hm" …) entfernen – per Regel, ohne KI.

Gemessen: Whisper schreibt diese Laute meist als "eh", "ehm" oder "Hm", selten als "äh".
"eh" ist aber auch ein normales Wort ("Das mache ich eh morgen" = sowieso). Es wird deshalb
nur entfernt, wenn es durch Satzzeichen abgetrennt ist ("…, eh, …" oder "Eh, …").

Wörter wie "also", "quasi" oder "halt" bleiben: Sie haben oft eine echte Bedeutung,
das kann nur eine KI im Zusammenhang unterscheiden.
"""

from __future__ import annotations

import re

# Eindeutige Laute – auch mit gedehnten Buchstaben ("ähhm", "hmmm").
_ALWAYS = r"(?:ä+h+m*|ö+h+m*|e+h+m+|h+m+|m+h+m*)"


def remove_fillers(text: str) -> str:
    flags = re.IGNORECASE
    # Satzanfang: "Hm, passt das?" -> "Passt das?" ("eh" nur mit Komma dahinter).
    # Großgeschrieben wird nur, wo wirklich ein Füllwort wegfiel – ein weiterdiktierter
    # Satzteil ("und dann …") bleibt klein.
    text = re.sub(
        rf"(^|[.!?]\s+)(?:{_ALWAYS}\b,?|eh\b,)\s*(\w?)",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
        flags=flags,
    )
    # Vor Satzzeichen: "morgen, ehm, also" -> "morgen, also" (ein Komma bleibt).
    # "eh" nur, wenn es auf BEIDEN Seiten abgetrennt ist – "Das mache ich eh." bleibt.
    text = re.sub(rf"\s*\b{_ALWAYS}\b\s*(?=[,.;:!?])", "", text, flags=flags)
    text = re.sub(r"(?<=,)\s*\beh\b\s*(?=[,.;:!?])", "", text, flags=flags)
    text = re.sub(r",\s*,", ",", text)
    # Mitten im Satz (nicht "eh"): "dir äh nur" -> "dir nur"
    text = re.sub(rf"\s+\b{_ALWAYS}\b,?(?=\s|$)", "", text, flags=flags).strip()
    # Bestand das Diktat nur aus Füllwörtern ("Ähm."), bleibt kein Text übrig.
    return text if re.search(r"\w", text) else ""
