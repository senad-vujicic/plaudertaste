"""Mikrofone auflisten und per Namen wiederfinden.

Gespeichert wird der Name, nicht die Nummer: Windows nummeriert Geräte neu,
sobald man etwas ein- oder aussteckt. Wir nutzen nur die Standard-Audioschnittstelle
(unter Windows MME) – die anderen listen dieselben Geräte doppelt.
"""

from __future__ import annotations

import sounddevice as sd

# MME-Eintrag, der nur auf das Windows-Standardgerät verweist ("Windows-Standard" in der Liste).
_DEFAULT_MAPPER_PREFIX = "Microsoft Soundmapper"


def _input_devices() -> list[tuple[int, str]]:
    api = sd.query_hostapis(sd.default.hostapi)
    devices = []
    for index in api["devices"]:
        info = sd.query_devices(index)
        if info["max_input_channels"] > 0 and not info["name"].startswith(_DEFAULT_MAPPER_PREFIX):
            devices.append((index, info["name"]))
    return devices


def list_microphones() -> list[str]:
    """Namen aller Mikrofone, ohne Duplikate, in der Reihenfolge von Windows."""
    return list(dict.fromkeys(name for _, name in _input_devices()))


def find_microphone(name: str) -> int | None:
    """Geräte-Nummer zum Namen. None = Windows-Standard (leerer Name oder Gerät nicht da)."""
    if not name:
        return None
    for index, device_name in _input_devices():
        if device_name == name:
            return index
    return None
