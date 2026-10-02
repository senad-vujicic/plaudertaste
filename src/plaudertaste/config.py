"""Laden, Prüfen und Anlegen der Konfigurationsdatei (TOML)."""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import tomli_w

VALID_MODELS = frozenset(
    {"auto", "tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"}
)
VALID_DEVICES = frozenset({"auto", "cpu", "cuda"})

# Kommentare, die beim Speichern über jeden Eintrag geschrieben werden.
_COMMENTS: dict[str, str] = {
    "hotkey": (
        "Taste(n), die zum Sprechen gehalten werden. Mehrere mit '+' verbinden.\n"
        "Beispiele: \"ctrl_r\" (rechte Strg), \"f9\", \"ctrl+cmd\" (Strg + Win)"
    ),
    "language": "Sprache als ISO-Code (z. B. \"de\", \"en\") oder \"auto\" für automatische Erkennung",
    "model": (
        "Whisper-Modell: \"auto\", \"tiny\", \"base\", \"small\", \"medium\", "
        "\"large-v3\", \"large-v3-turbo\"\n"
        "\"auto\" = large-v3-turbo mit NVIDIA-GPU, sonst small"
    ),
    "device": "Rechengerät: \"auto\", \"cpu\" oder \"cuda\" (NVIDIA-GPU)",
    "microphone": "Mikrofon-Name wie in den Einstellungen angezeigt, \"\" = Windows-Standard",
    "sound": "Kurzer Ton bei Start und Ende der Aufnahme: true oder false",
    "overlay": "Anzeige unten am Bildschirm während Aufnahme und Verarbeitung: true oder false",
    "voice_commands": (
        "Sprachbefehle \"neue Zeile\", \"neuer Absatz\", \"Komma\", \"Fragezeichen\", "
        "\"Ausrufezeichen\", \"Doppelpunkt\": true oder false"
    ),
}
_TYPE_HINTS = {str: "ein Text in Anführungszeichen", bool: "true oder false"}


class ConfigError(Exception):
    """Die Konfigurationsdatei ist ungültig."""


@dataclass(frozen=True)
class Config:
    hotkey: str = "ctrl_r"
    language: str = "de"
    model: str = "auto"
    device: str = "auto"
    microphone: str = ""
    sound: bool = True
    overlay: bool = True
    voice_commands: bool = True


def render_config(config: Config) -> str:
    """Erzeugt den Inhalt einer kommentierten Config-Datei."""
    blocks = []
    for key, value in asdict(config).items():
        comment = "\n".join(f"# {line}" for line in _COMMENTS[key].splitlines())
        blocks.append(f"{comment}\n{tomli_w.dumps({key: value})}")
    return "\n".join(blocks)


def parse_config(data: dict[str, object]) -> Config:
    """Prüft die Rohdaten aus der TOML-Datei und baut daraus eine Config."""
    known = {f.name for f in fields(Config)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise ConfigError(f"Unbekannte Einträge: {', '.join(unknown)}")

    defaults = Config()
    for key, value in data.items():
        expected = type(getattr(defaults, key))
        if not isinstance(value, expected):
            raise ConfigError(f"'{key}' muss {_TYPE_HINTS[expected]} sein.")

    config = Config(**{k: v.strip() if isinstance(v, str) else v for k, v in data.items()})  # type: ignore[arg-type]

    if not config.hotkey:
        raise ConfigError("'hotkey' darf nicht leer sein.")
    if config.model not in VALID_MODELS:
        raise ConfigError(
            f"Unbekanntes Modell '{config.model}'. Erlaubt: {', '.join(sorted(VALID_MODELS))}"
        )
    if config.device not in VALID_DEVICES:
        raise ConfigError(
            f"Unbekanntes Gerät '{config.device}'. Erlaubt: {', '.join(sorted(VALID_DEVICES))}"
        )
    if not config.language:
        raise ConfigError("'language' darf nicht leer sein.")
    return config


def load_config(path: Path) -> Config:
    """Lädt die Config. Fehlt die Datei, wird sie mit Standardwerten angelegt."""
    if not path.exists():
        save_config(path, Config())
        return Config()

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Fehler in {path}: {exc}") from exc
    return parse_config(data)


def save_config(path: Path, config: Config) -> None:
    """Speichert die Config – mit Kommentaren, damit sie von Hand lesbar bleibt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_config(config), encoding="utf-8")
