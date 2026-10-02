"""Auswahllisten für die Einstellungen: Whisper-Modelle und Sprachen."""

from __future__ import annotations

from dataclasses import dataclass

from faster_whisper import download_model
from faster_whisper.tokenizer import _LANGUAGE_CODES  # nur intern verfügbar, per Test abgesichert
from PySide6.QtCore import QLocale


@dataclass(frozen=True)
class ModelInfo:
    name: str
    size_mb: int  # Download-Größe laut Hugging Face (Stand 10/2026)
    hint: str


MODELS: tuple[ModelInfo, ...] = (
    ModelInfo("tiny", 78, "sehr schnell, ungenau"),
    ModelInfo("base", 148, "schnell, für Deutsch eher ungenau"),
    ModelInfo("small", 486, "schnell, gut für CPU"),
    ModelInfo("medium", 1531, "genauer, auf CPU langsam"),
    ModelInfo("large-v3-turbo", 1622, "beste Wahl mit NVIDIA-GPU"),
    ModelInfo("large-v3", 3091, "höchste Genauigkeit, langsam"),
)

AUTO = "auto"
# Whisper nutzt für Javanisch den veralteten Code "jw" – Qt kennt nur den ISO-Code "jv".
_QT_LANGUAGE_CODES = {"jw": "jv"}
# Oben angeheftet, mit festen Namen (Qt nennt "en" sonst "American English").
_PINNED_LANGUAGES = {"de": "Deutsch", "en": "English"}


def is_model_downloaded(name: str) -> bool:
    """Liegt das Modell schon lokal vor? Fragt nur den Cache ab, lädt nichts herunter."""
    try:
        download_model(name, local_files_only=True)
    except Exception:  # huggingface_hub meldet "nicht im Cache" mit eigenen Fehlertypen
        return False
    return True


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


def language_options() -> list[tuple[str, str]]:
    """(Code, Anzeigename): automatisch, Deutsch, Englisch, dann alphabetisch."""
    pinned = list(_PINNED_LANGUAGES.items())
    rest = sorted(
        ((code, language_name(code)) for code in _LANGUAGE_CODES if code not in _PINNED_LANGUAGES),
        key=lambda item: item[1].casefold(),
    )
    return [(AUTO, "Automatisch erkennen"), *pinned, *rest]


def language_display(code: str) -> str:
    """Anzeigename für einen Config-Wert, z. B. "de" -> "Deutsch"."""
    return dict(language_options()).get(code, code)
