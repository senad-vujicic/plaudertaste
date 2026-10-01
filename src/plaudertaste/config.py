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

# Kommentare, die beim Anlegen der Datei über jeden Eintrag geschrieben werden.
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
}


class ConfigError(Exception):
    """Die Konfigurationsdatei ist ungültig."""


@dataclass(frozen=True)
class Config:
    hotkey: str = "ctrl_r"
    language: str = "de"
    model: str = "auto"
    device: str = "auto"


def render_default_config() -> str:
    """Erzeugt den Inhalt einer kommentierten Config-Datei mit Standardwerten."""
    blocks = []
    for key, value in asdict(Config()).items():
        comment = "\n".join(f"# {line}" for line in _COMMENTS[key].splitlines())
        blocks.append(f"{comment}\n{tomli_w.dumps({key: value})}")
    return "\n".join(blocks)


def parse_config(data: dict[str, object]) -> Config:
    """Prüft die Rohdaten aus der TOML-Datei und baut daraus eine Config."""
    known = {f.name for f in fields(Config)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise ConfigError(f"Unbekannte Einträge: {', '.join(unknown)}")

    for key, value in data.items():
        if not isinstance(value, str):
            raise ConfigError(f"'{key}' muss ein Text in Anführungszeichen sein.")

    config = Config(**{k: v.strip() for k, v in data.items()})  # type: ignore[union-attr]

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
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_default_config(), encoding="utf-8")
        return Config()

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Fehler in {path}: {exc}") from exc
    return parse_config(data)
