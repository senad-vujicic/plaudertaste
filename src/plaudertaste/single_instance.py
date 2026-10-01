"""Verhindert, dass Plaudertaste zweimal läuft (sonst würde jeder Text doppelt eingefügt)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLockFile


def acquire_single_instance_lock(path: Path) -> QLockFile | None:
    """Gibt die gehaltene Sperre zurück oder None, wenn schon eine Instanz läuft.

    Die Sperre muss bis Programmende referenziert bleiben. Stürzt das Programm ab,
    erkennt Qt die verwaiste Sperre am nicht mehr laufenden Prozess.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(path))
    lock.setStaleLockTime(0)  # nie wegen Alter aufheben – nur wenn der Prozess weg ist
    return lock if lock.tryLock(100) else None
