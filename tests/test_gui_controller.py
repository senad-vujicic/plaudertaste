from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from plaudertaste import autostart, gui, paths
from plaudertaste.config import Config, load_config
from plaudertaste.hotkey import HotkeyCapture
from plaudertaste.main_window import Page
from plaudertaste.settings_page import Settings


class FakeApp:
    def __init__(self) -> None:
        self.languages: list[str | None] = []

    def set_language(self, language: str | None) -> None:
        self.languages.append(language)

    def on_start(self) -> None: ...
    def on_stop(self) -> None: ...
    def on_cancel(self) -> None: ...


@pytest.fixture
def controller(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[gui.Controller]:
    # Nichts Echtes anfassen: Config, Statistik, Registry, Mikrofone, Modell-Cache.
    monkeypatch.setattr(paths, "config_file", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(paths, "stats_file", lambda: tmp_path / "stats.json")
    registry = {"enabled": False}
    monkeypatch.setattr(autostart, "is_enabled", lambda: registry["enabled"])
    monkeypatch.setattr(autostart, "set_enabled", lambda value: registry.update(enabled=value))
    monkeypatch.setattr(gui, "list_microphones", lambda: ["Headset (USB)"])
    monkeypatch.setattr(gui, "is_model_downloaded", lambda name: name == "small")

    controller = gui.Controller(Config(), tmp_path / "app.log")
    controller.loads: list[Config] = []  # type: ignore[attr-defined]
    monkeypatch.setattr(
        controller, "_load_model_in_background", lambda: controller.loads.append(controller._config)  # type: ignore[attr-defined]
    )
    controller._app = FakeApp()  # type: ignore[assignment]
    controller._activate_push_to_talk()
    yield controller
    controller.window.deleteLater()


def test_settings_are_saved_to_file(controller: gui.Controller) -> None:
    new = replace(Config(), sound=False, microphone="Headset (USB)")

    controller.apply_settings(Settings(new, autostart=False))

    assert load_config(paths.config_file()) == new
    assert controller._recorder.microphone == "Headset (USB)"
    assert not controller.tray.sound_action.isChecked()
    assert controller.window.start_page.microphone_label.text() == "Headset (USB)"


def test_autostart_is_switched(controller: gui.Controller) -> None:
    controller.apply_settings(Settings(Config(), autostart=True))

    assert autostart.is_enabled()


def test_hotkey_change_rebuilds_push_to_talk(controller: gui.Controller) -> None:
    old_target = controller._key_target

    controller.apply_settings(Settings(replace(Config(), hotkey="f9"), autostart=False))

    assert controller._key_target is not old_target
    assert controller._key_target._combo == frozenset({"f9"})  # type: ignore[union-attr]
    assert controller.tray._hotkey_label == "F9"
    assert "<b>F9</b>" in controller.window.start_page.instructions.text()


def test_language_change_does_not_reload_model(controller: gui.Controller) -> None:
    controller.apply_settings(Settings(replace(Config(), language="en"), autostart=False))

    assert controller._app.languages == ["en"]  # type: ignore[union-attr]
    assert controller.loads == []  # type: ignore[attr-defined]
    assert controller.window.start_page.language_label.text() == "English"


def test_model_change_reloads_in_background(controller: gui.Controller) -> None:
    controller.apply_settings(Settings(replace(Config(), model="medium"), autostart=False))

    assert [c.model for c in controller.loads] == ["medium"]  # type: ignore[attr-defined]


def test_failed_model_change_restores_previous_model(
    controller: gui.Controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gui.QMessageBox, "warning", lambda *args: None)
    controller.apply_settings(Settings(replace(Config(), model="medium"), autostart=False))

    controller._on_model_failed("Download abgebrochen")

    assert controller._config.model == "auto"
    assert load_config(paths.config_file()).model == "auto"


def test_hotkey_capture_pauses_dictation(controller: gui.Controller) -> None:
    push_to_talk = controller._key_target

    controller._start_hotkey_capture()
    assert isinstance(controller._key_target, HotkeyCapture)

    controller._on_hotkey_captured("f9")
    assert controller._key_target is push_to_talk


def test_dictation_updates_history_stats_and_start_page(controller: gui.Controller) -> None:
    controller._on_dictation_finished("Hallo liebe Welt", 2.0)

    assert [e.text for e in controller._history.entries()] == ["Hallo liebe Welt"]
    assert controller._stats.today().words == 3
    assert controller.window.start_page.words_value.text() == "3"
    assert controller.window.start_page.dictations_value.text() == "1"
    assert controller.window.stats_page.words(0) == "3"  # Spalte "Heute"


def test_closing_window_hides_it_and_hints_once(
    controller: gui.Controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[str] = []
    monkeypatch.setattr(controller.tray, "showMessage", lambda title, text, icon: messages.append(text))
    controller.show_window(Page.START)

    controller.window.close()
    controller.show_window(Page.START)
    controller.window.close()

    assert not controller.window.isVisible()
    assert len(messages) == 1


def test_settings_page_shows_saved_values_when_opened(controller: gui.Controller) -> None:
    controller._save_config(replace(Config(), model="small"))

    controller.show_window(Page.SETTINGS)

    assert controller.window.current_page() is Page.SETTINGS
    assert controller.settings_page.settings().config.model == "small"
    assert "✓ heruntergeladen" in controller.settings_page.model_box.currentText()


def test_saving_shows_confirmation(controller: gui.Controller) -> None:
    controller.show_window(Page.SETTINGS)
    page = controller.settings_page
    page.sound_check.setChecked(False)
    assert page.save_button.isEnabled()

    page.save_button.click()

    assert not page.saved_label.isHidden()
    assert not page.save_button.isEnabled()  # gespeichert = nichts mehr offen
