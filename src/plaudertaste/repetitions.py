"""Sicherheitsnetz gegen Wiederholungsschleifen von Whisper.

Whisper gerät bei langen Aufnahmen gelegentlich in eine Schleife und gibt denselben Satz
immer wieder aus ("Und dann geht's, was ich meine." ×20). Die Hauptursache ist in
transcriber.py abgeschaltet; was trotzdem durchrutscht, fängt diese Bereinigung ab.

Regel: Steht derselbe Satz mindestens dreimal direkt hintereinander, bleibt er einmal stehen.
Kurze Sätze ("Ja. Ja. Ja.") bleiben unangetastet – die sagt man auch mal absichtlich.
"""

from __future__ import annotations

import re

MIN_REPEATS = 3
MIN_WORDS = 3

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _key(sentence: str) -> str:
    """Vergleichsform: ohne Satzzeichen, Groß-/Kleinschreibung egal."""
    return re.sub(r"\W+", " ", sentence).strip().casefold()


def remove_repeated_sentences(text: str) -> str:
    sentences = _SENTENCE_END.split(text.strip())
    kept: list[str] = []
    i = 0
    while i < len(sentences):
        key = _key(sentences[i])
        run = 1
        while i + run < len(sentences) and _key(sentences[i + run]) == key:
            run += 1
        is_loop = run >= MIN_REPEATS and len(key.split()) >= MIN_WORDS
        kept.extend(sentences[i : i + (1 if is_loop else run)])
        i += run
    return " ".join(kept)
