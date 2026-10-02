"""Anzeige für die Einstellungen: Modell-Beschriftungen und die Sprachliste."""

from __future__ import annotations

from functools import cache

from faster_whisper.tokenizer import _LANGUAGE_CODES  # nur intern verfügbar, per Test abgesichert
from PySide6.QtCore import QLocale

from plaudertaste.config import AUTO
from plaudertaste.models import AUTO_MODEL, ModelInfo

AUTO_MODEL_LABEL = f"Automatisch – {AUTO_MODEL['cuda']} mit NVIDIA-GPU, sonst {AUTO_MODEL['cpu']}"
# Whisper nutzt für Javanisch den veralteten Code "jw" – Qt kennt nur den ISO-Code "jv".
_QT_LANGUAGE_CODES = {"jw": "jv"}
# Oben angeheftet, mit festen Namen (Qt nennt "en" sonst "American English").
_PINNED_LANGUAGES = {"de": "Deutsch", "en": "English"}


def format_size(size_mb: int) -> str:
    """Deutsche Schreibweise: unter 1 GB in MB, sonst GB mit einer Nachkommastelle."""
    if size_mb < 1000:
        return f"{size_mb} MB"
    return f"{size_mb / 1000:.1f} GB".replace(".", ",")


def model_label(info: ModelInfo, downloaded: bool) -> str:
    mark = " ✓ heruntergeladen" if downloaded else ""
    return f"{info.name} – {format_size(info.size_mb)}, {info.hint}{mark}"


def language_name(code: str) -> str:
    """Name einer Sprache in ihrer eigenen Schrift, ergänzt um den englischen Namen."""
    locale = QLocale(_QT_LANGUAGE_CODES.get(code, code))
    if locale.language() == QLocale.Language.C:
        return code
    native = locale.nativeLanguageName()
    native = native[:1].upper() + native[1:]
    english = QLocale.languageToString(locale.language())
    return native if native.casefold() == english.casefold() else f"{native} ({english})"


@cache  # ~100 Sprachnamen über Qt – einmal berechnen genügt
def language_options() -> tuple[tuple[str, str], ...]:
    """(Code, Anzeigename): automatisch, Deutsch, Englisch, dann alphabetisch.

    Ein Tupel, weil das Ergebnis zwischengespeichert wird und für alle gleich bleiben muss."""
    pinned = list(_PINNED_LANGUAGES.items())
    rest = sorted(
        ((code, language_name(code)) for code in _LANGUAGE_CODES if code not in _PINNED_LANGUAGES),
        key=lambda item: item[1].casefold(),
    )
    return ((AUTO, "Automatisch erkennen"), *pinned, *rest)


def language_display(code: str) -> str:
    """Anzeigename für einen Config-Wert, z. B. "de" -> "Deutsch"."""
    return dict(language_options()).get(code, code)
