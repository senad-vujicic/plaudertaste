import pytest
from PySide6.QtWidgets import QApplication

from plaudertaste.config import Config
from plaudertaste.settings_dialog import WAITING_TEXT, SettingsDialog

pytestmark = pytest.mark.usefixtures("qapp")

MICS = ["INPUT 1/2 (2- Volt 2)", "Headset (USB)"]


def make_dialog(config: Config = Config(), autostart: bool = False) -> SettingsDialog:
    return SettingsDialog(config, autostart, MICS, downloaded_models={"small"})


def test_unchanged_dialog_returns_same_settings() -> None:
    config = Config(model="small", language="en", microphone="Headset (USB)", sound=False)

    settings = make_dialog(config, autostart=True).settings()

    assert settings.config == config
    assert settings.autostart is True


def test_changes_are_returned() -> None:
    dialog = make_dialog()
    dialog.model_box.setCurrentIndex(dialog.model_box.findData("medium"))
    dialog.language_box.setCurrentIndex(dialog.language_box.findData("fr"))
    dialog.microphone_box.setCurrentIndex(dialog.microphone_box.findData("INPUT 1/2 (2- Volt 2)"))
    dialog.overlay_check.setChecked(False)
    dialog.autostart_check.setChecked(True)

    settings = dialog.settings()

    assert settings.config == Config(
        model="medium", language="fr", microphone="INPUT 1/2 (2- Volt 2)", overlay=False
    )
    assert settings.autostart is True


def test_missing_microphone_is_kept_and_marked() -> None:
    dialog = make_dialog(Config(microphone="Altes Mikro"))

    assert dialog.microphone_box.currentText() == "Altes Mikro (nicht verbunden)"
    assert dialog.settings().config.microphone == "Altes Mikro"


def test_download_hint_only_for_missing_models() -> None:
    dialog = make_dialog()

    dialog.model_box.setCurrentIndex(dialog.model_box.findData("small"))  # schon geladen
    assert dialog.model_hint.isHidden()
    dialog.model_box.setCurrentIndex(dialog.model_box.findData("large-v3"))
    assert not dialog.model_hint.isHidden()
    assert "3,1 GB" in dialog.model_hint.text()


def test_hotkey_capture_flow() -> None:
    dialog = make_dialog()
    requests: list[bool] = []
    dialog.capture_requested.connect(lambda: requests.append(True))

    dialog.hotkey_button.click()
    assert requests == [True]
    assert dialog.hotkey_button.text() == WAITING_TEXT

    dialog.set_captured_hotkey("ctrl_l+cmd")

    assert dialog.hotkey_button.text() == "Linke Strg + Win"
    assert dialog.settings().config.hotkey == "ctrl_l+cmd"


def test_unsuitable_hotkey_is_rejected_with_hint() -> None:
    dialog = make_dialog()
    dialog.hotkey_button.click()

    dialog.set_captured_hotkey("a")

    assert dialog.settings().config.hotkey == "ctrl_r"  # alter Hotkey bleibt
    assert dialog.hotkey_button.text() == "Rechte Strg"
    assert "beim Schreiben gebraucht" in dialog.hotkey_hint.text()


def test_keys_are_swallowed_while_waiting(qapp: QApplication) -> None:
    """Enter darf während der Hotkey-Aufnahme nicht "Speichern" auslösen."""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    dialog = make_dialog()
    dialog.hotkey_button.click()
    enter = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)

    QApplication.sendEvent(dialog.hotkey_button, enter)

    assert dialog.result() == 0 and dialog.hotkey_button.waiting
    dialog.reject()
