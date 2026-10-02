import contextlib
import sys
import winreg
from collections.abc import Iterator
from pathlib import Path

import pytest

from plaudertaste import autostart

# Eigener Testschlüssel – der echte Autostart-Schlüssel wird nie angefasst.
TEST_KEY = r"Software\PlaudertasteTests\Run"


@pytest.fixture
def key() -> Iterator[str]:
    yield TEST_KEY
    for path in (TEST_KEY, r"Software\PlaudertasteTests"):
        with contextlib.suppress(FileNotFoundError):
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)


def read_value(key_path: str) -> str:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as handle:
        return winreg.QueryValueEx(handle, autostart.VALUE_NAME)[0]


def test_enable_and_disable(key: str) -> None:
    assert not autostart.is_enabled(key)

    autostart.set_enabled(True, key)
    assert autostart.is_enabled(key)
    assert read_value(key) == autostart.startup_command()

    autostart.set_enabled(False, key)
    assert not autostart.is_enabled(key)


def test_disable_when_already_off_is_harmless(key: str) -> None:
    autostart.set_enabled(False, key)

    assert not autostart.is_enabled(key)


def test_dev_command_uses_pythonw_without_console() -> None:
    command = autostart.startup_command()

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    assert command == f'"{pythonw}" -m plaudertaste --background'
    assert Path(sys.executable).with_name("pythonw.exe").exists()


def test_frozen_command_uses_exe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Programme\Plaudertaste\Plaudertaste.exe")

    assert (
        autostart.startup_command() == r'"C:\Programme\Plaudertaste\Plaudertaste.exe" --background'
    )
