"""Eigenes Wörterbuch: Begriffe als Hinweis für Whisper und feste Ersetzungen danach.

Gespeichert in woerterbuch.toml neben der config.toml – so lässt es sich leicht sichern
oder mit anderen teilen.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w

from plaudertaste.storage import write_text_atomic

# Whisper nimmt nur ~224 Sprachbausteine als Hinweis auf; grob geschätzt passen so viele
# Zeichen sicher hinein. Darüber werden Begriffe womöglich nicht mehr berücksichtigt.
MAX_HINT_CHARS = 600

_HEADER = """\
# Plaudertaste – eigenes Wörterbuch
#
# terms: Namen und Fachbegriffe, die Whisper richtig erkennen und schreiben soll.
# replacements: Nach der Erkennung wird "spoken" durch "written" ersetzt
#               (nur ganze Wörter, Groß-/Kleinschreibung egal).

"""


class DictionaryError(Exception):
    """Die Wörterbuch-Datei ist ungültig."""


@dataclass(frozen=True)
class Replacement:
    spoken: str
    written: str


@dataclass(frozen=True)
class Dictionary:
    terms: tuple[str, ...] = ()
    replacements: tuple[Replacement, ...] = ()

    def hotwords(self) -> str | None:
        """Begriffe als Hinweis für Whisper – None, wenn es keine gibt."""
        return ", ".join(self.terms) or None

    def hint_too_long(self) -> bool:
        return len(self.hotwords() or "") > MAX_HINT_CHARS

    def apply(self, text: str) -> str:
        """Ersetzungen anwenden: ganze Wörter, Groß-/Kleinschreibung egal."""
        # Längere zuerst, damit "mfg lg" nicht vorher von "mfg" zerstückelt wird.
        for replacement in sorted(self.replacements, key=lambda r: -len(r.spoken)):
            words = (re.escape(word) for word in replacement.spoken.split())
            pattern = r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)"
            if "\n" in replacement.written:
                # Textbaustein (z. B. Signatur): Whispers Satzzeichen dahinter ("Meine
                # Signatur.") fällt weg, sonst stünde es einsam unter dem Baustein.
                pattern += r"[.,;:!?]?"
            # Funktion statt Text als Ersatz: so werden "\1" o. Ä. im Ersatz nicht ausgewertet.
            # Der Wert wird fest gebunden (written=…), nicht über die Schleifenvariable gelesen.
            text = re.sub(
                pattern,
                lambda _, written=replacement.written: written,
                text,
                flags=re.IGNORECASE,
            )
        return text

    def with_term(self, term: str) -> Dictionary:
        term = term.strip()
        if not term or term.casefold() in (t.casefold() for t in self.terms):
            return self
        return Dictionary((*self.terms, term), self.replacements)

    def without_term(self, term: str) -> Dictionary:
        return Dictionary(tuple(t for t in self.terms if t != term), self.replacements)

    def with_replacement(self, spoken: str, written: str) -> Dictionary:
        spoken, written = spoken.strip(), written.strip()
        if not spoken or not written:
            return self
        # Gleiches "gesagt" ersetzt den alten Eintrag, statt ihn zu doppeln.
        others = tuple(r for r in self.replacements if r.spoken.casefold() != spoken.casefold())
        return Dictionary(self.terms, (*others, Replacement(spoken, written)))

    def without_replacement(self, spoken: str) -> Dictionary:
        return Dictionary(self.terms, tuple(r for r in self.replacements if r.spoken != spoken))


def load_dictionary(path: Path) -> Dictionary:
    """Lädt das Wörterbuch. Fehlt die Datei, ist es einfach leer."""
    if not path.exists():
        return Dictionary()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        terms = data.get("terms", [])
        replacements = data.get("replacements", [])
        if not all(isinstance(t, str) for t in terms):
            raise DictionaryError("'terms' darf nur Texte enthalten.")
        return Dictionary(
            tuple(terms),
            tuple(Replacement(str(r["spoken"]), str(r["written"])) for r in replacements),
        )
    except tomllib.TOMLDecodeError as exc:
        raise DictionaryError(f"Fehler in {path}: {exc}") from exc
    except (KeyError, TypeError) as exc:
        raise DictionaryError(
            f"Fehler in {path}: Ersetzungen brauchen 'spoken' und 'written'."
        ) from exc


def save_dictionary(path: Path, dictionary: Dictionary) -> None:
    data = {
        "terms": list(dictionary.terms),
        "replacements": [
            {"spoken": r.spoken, "written": r.written} for r in dictionary.replacements
        ],
    }
    write_text_atomic(path, _HEADER + tomli_w.dumps(data))
