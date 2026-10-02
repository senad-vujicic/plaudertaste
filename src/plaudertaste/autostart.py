"""Autostart mit Windows über die Registry (nur für den aktuellen Benutzer, ohne Admin-Rechte).

Die Registry ist die einzige Quelle der Wahrheit – der Zustand wird nicht zusätzlich
in der Config gespeichert, damit beides nie auseinanderlaufen kann.
"""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Plaudertaste"


def startup_command() -> str:
    """Befehl, mit dem Windows Plaudertaste nach der Anmeldung startet."""
    if getattr(sys, "frozen", False):  # gebaute .exe (PyInstaller)
        return f'"{sys.executable}"'
    # Entwicklung: pythonw.exe statt python.exe – startet ohne Konsolenfenster.
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" -m plaudertaste'


def is_enabled(key_path: str = RUN_KEY) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return False
    return True


def set_enabled(enabled: bool, key_path: str = RUN_KEY) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass  # war schon aus
