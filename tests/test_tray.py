from pathlib import Path

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from plaudertaste.app import Status
from plaudertaste.tray import STATUS_COLORS, Tray, _draw_bubble, make_icon


@pytest.mark.usefixtures("qapp")
@pytest.mark.parametrize("status", list(Status))
def test_icon_exists_for_every_status(status: Status) -> None:
    icon = make_icon(status)

    assert not icon.isNull()
    assert len(icon.availableSizes()) == 5


@pytest.mark.usefixtures("qapp")
def test_recording_icon_is_red_and_loading_icon_is_hollow() -> None:
    center = (32, 40)  # unterhalb der drei Punkte, innerhalb der Blase

    recording = _draw_bubble(Status.RECORDING, 64).toImage().pixelColor(*center)
    loading = _draw_bubble(Status.LOADING, 64).toImage().pixelColor(*center)

    assert recording.name() == QColor(STATUS_COLORS[Status.RECORDING]).name()
    assert loading.alpha() == 0  # nur Umriss, innen durchsichtig


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
