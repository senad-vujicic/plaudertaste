"""Speicherorte der App im Benutzerordner."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Plaudertaste"


def _env_dir(variable: str, fallback: Path) -> Path:
    value = os.environ.get(variable)
    return (Path(value) if value else fallback) / APP_NAME


def config_dir() -> Path:
    """%APPDATA%\\Plaudertaste – Einstellungen (wandern bei Firmen-Konten mit)."""
    return _env_dir("APPDATA", Path.home() / ".config")


def local_dir() -> Path:
    """%LOCALAPPDATA%\\Plaudertaste – rechnerbezogene Daten wie Logs und Lock-Datei."""
    return _env_dir("LOCALAPPDATA", Path.home() / ".local" / "state")


def config_file() -> Path:
    return config_dir() / "config.toml"


def log_dir() -> Path:
    return local_dir() / "logs"


def stats_file() -> Path:
    return local_dir() / "stats.json"


def lock_file() -> Path:
    return local_dir() / "plaudertaste.lock"
