from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from plaudertaste.app import Status
from plaudertaste.tray import Tray


def test_tray_texts_follow_status(qapp: QApplication, tmp_path: Path) -> None:
    tray = Tray("Rechte Strg", True, True, tmp_path / "config.toml", tmp_path / "app.log")

    assert tray.toolTip() == "Plaudertaste – Modell wird geladen …"
    tray.set_status(Status.READY)
    assert tray.toolTip() == "Plaudertaste – Bereit – Rechte Strg halten zum Sprechen"
    tray.set_status(Status.RECORDING)
    assert tray.toolTip() == "Plaudertaste – Aufnahme läuft"


def test_sound_menu_entry_reports_toggle(qapp: QApplication, tmp_path: Path) -> None:
    tray = Tray("Rechte Strg", True, True, tmp_path / "config.toml", tmp_path / "app.log")
    toggles: list[bool] = []
    tray.sound_toggled.connect(toggles.append)

    assert tray.sound_action.isChecked()
    tray.sound_action.trigger()  # wie ein Klick im Menü

    assert toggles == [False]


def test_set_toggles_does_not_emit_signals(qapp: QApplication, tmp_path: Path) -> None:
    tray = Tray("Rechte Strg", True, True, tmp_path / "config.toml", tmp_path / "app.log")
    emitted: list[bool] = []
    tray.sound_toggled.connect(emitted.append)
    tray.overlay_toggled.connect(emitted.append)

    tray.set_toggles(sound=False, overlay=False)

    assert emitted == []
    assert not tray.sound_action.isChecked() and not tray.overlay_action.isChecked()


def test_double_click_opens_window(qapp: QApplication, tmp_path: Path) -> None:
    tray = Tray("Rechte Strg", True, True, tmp_path / "config.toml", tmp_path / "app.log")
    requests: list[bool] = []
    tray.open_requested.connect(lambda: requests.append(True))

    tray.activated.emit(QSystemTrayIcon.ActivationReason.DoubleClick)
    tray.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)  # einfacher Klick: nichts

    assert requests == [True]
