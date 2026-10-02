import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from plaudertaste.config import Config
from plaudertaste.settings_page import WAITING_TEXT, Settings, SettingsPage

pytestmark = pytest.mark.usefixtures("qapp")

MICS = ["INPUT 1/2 (2- Volt 2)", "Headset (USB)"]


def make_page(config: Config = Config(), autostart: bool = False) -> SettingsPage:
    page = SettingsPage()
    page.load(config, autostart, MICS, downloaded_models={"small"})
    return page


def test_unchanged_page_returns_same_settings() -> None:
    config = Config(model="small", language="en", microphone="Headset (USB)", sound=False)

    settings = make_page(config, autostart=True).settings()

    assert settings == Settings(config, autostart=True)


def test_changes_are_returned_on_save() -> None:
    page = make_page()
    saved: list[Settings] = []
    page.save_requested.connect(saved.append)
    page.model_box.setCurrentIndex(page.model_box.findData("medium"))
    page.language_box.setCurrentIndex(page.language_box.findData("fr"))
    page.microphone_box.setCurrentIndex(page.microphone_box.findData("INPUT 1/2 (2- Volt 2)"))
    page.overlay_check.setChecked(False)
    page.autostart_check.setChecked(True)

    page.save_button.click()

    assert saved == [
        Settings(
            Config(model="medium", language="fr", microphone="INPUT 1/2 (2- Volt 2)", overlay=False),
            autostart=True,
        )
    ]


def test_discard_restores_saved_state() -> None:
    page = make_page()
    page.model_box.setCurrentIndex(page.model_box.findData("medium"))
    page.sound_check.setChecked(False)

    page.discard_button.click()

    assert page.settings() == Settings(Config(), autostart=False)


def test_missing_microphone_is_kept_and_marked() -> None:
    page = make_page(Config(microphone="Altes Mikro"))

    assert page.microphone_box.currentText() == "Altes Mikro (nicht verbunden)"
    assert page.settings().config.microphone == "Altes Mikro"


def test_download_hint_only_for_missing_models() -> None:
    page = make_page()

    page.model_box.setCurrentIndex(page.model_box.findData("small"))  # schon geladen
    assert page.model_hint.isHidden()
    page.model_box.setCurrentIndex(page.model_box.findData("large-v3"))
    assert not page.model_hint.isHidden()
    assert "3,1 GB" in page.model_hint.text()


def test_hotkey_capture_flow() -> None:
    page = make_page()
    requests: list[bool] = []
    page.capture_requested.connect(lambda: requests.append(True))

    page.hotkey_button.click()
    assert requests == [True]
    assert page.hotkey_button.text() == WAITING_TEXT

    page.set_captured_hotkey("ctrl_l+cmd")

    assert page.hotkey_button.text() == "Linke Strg + Win"
    assert page.settings().config.hotkey == "ctrl_l+cmd"


def test_unsuitable_hotkey_is_rejected_with_hint() -> None:
    page = make_page()
    page.hotkey_button.click()

    page.set_captured_hotkey("a")

    assert page.settings().config.hotkey == "ctrl_r"  # alter Hotkey bleibt
    assert page.hotkey_button.text() == "Rechte Strg"
    assert "beim Schreiben gebraucht" in page.hotkey_hint.text()


def test_cancel_capture_restores_button_and_reports() -> None:
    page = make_page()
    cancelled: list[bool] = []
    page.capture_cancelled.connect(lambda: cancelled.append(True))
    page.hotkey_button.click()

    page.cancel_capture()

    assert cancelled == [True]
    assert not page.hotkey_button.waiting
    assert page.hotkey_button.text() == "Rechte Strg"


def test_keys_are_swallowed_while_waiting(qapp: QApplication) -> None:
    """Enter darf während der Hotkey-Aufnahme keinen Knopf auslösen."""
    page = make_page()
    saved: list[Settings] = []
    page.save_requested.connect(saved.append)
    page.hotkey_button.click()
    enter = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)

    QApplication.sendEvent(page.hotkey_button, enter)

    assert saved == [] and page.hotkey_button.waiting
    page.cancel_capture()


def test_buttons_only_active_with_changes() -> None:
    page = make_page()
    assert not page.save_button.isEnabled()
    assert not page.discard_button.isEnabled()

    page.sound_check.setChecked(False)
    assert page.save_button.isEnabled() and page.discard_button.isEnabled()

    page.sound_check.setChecked(True)  # zurück auf den gespeicherten Stand
    assert not page.save_button.isEnabled()


def test_captured_hotkey_counts_as_change() -> None:
    page = make_page()
    page.hotkey_button.click()

    page.set_captured_hotkey("f9")

    assert page.save_button.isEnabled()


def test_saved_confirmation_appears_and_fades(qapp: QApplication) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    from plaudertaste.ui import SavedIndicator

    page = make_page()
    page.saved_label.fade_delay.setInterval(10)  # im Test nicht 2,5 s warten
    page.saved_label.fade.setDuration(10)

    page.show_saved()
    assert not page.saved_label.isHidden()

    loop = QEventLoop()
    QTimer.singleShot(200, loop.quit)
    loop.exec()
    assert page.saved_label.isHidden()
    assert page.saved_label.text() == SavedIndicator.TEXT


def test_new_change_hides_old_confirmation() -> None:
    page = make_page()
    page.show_saved()

    page.overlay_check.setChecked(False)

    assert page.saved_label.isHidden()


def test_voice_commands_switch() -> None:
    page = make_page(Config(voice_commands=True))
    assert page.voice_commands_check.isChecked()

    page.voice_commands_check.setChecked(False)

    assert page.settings().config.voice_commands is False
    assert page.save_button.isEnabled()


def test_fillers_switch() -> None:
    page = make_page(Config(remove_fillers=True))

    page.fillers_check.setChecked(False)

    assert page.settings().config.remove_fillers is False


def test_update_check_switch() -> None:
    page = make_page(Config(check_updates=True))

    page.updates_check.setChecked(False)

    assert page.settings().config.check_updates is False
