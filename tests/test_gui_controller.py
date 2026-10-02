from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from plaudertaste import autostart, gui, paths
from plaudertaste.config import Config, load_config
from plaudertaste.hotkey import HotkeyCapture
from plaudertaste.settings_dialog import Settings


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
) -> gui.Controller:
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr(paths, "config_file", lambda: config_file)
    registry = {"enabled": False}
    monkeypatch.setattr(autostart, "is_enabled", lambda: registry["enabled"])
    monkeypatch.setattr(autostart, "set_enabled", lambda value: registry.update(enabled=value))

    controller = gui.Controller(Config(), tmp_path / "app.log")
    controller.loads: list[Config] = []  # type: ignore[attr-defined]
    monkeypatch.setattr(
        controller, "_load_model_in_background", lambda: controller.loads.append(controller._config)  # type: ignore[attr-defined]
    )
    controller._app = FakeApp()  # type: ignore[assignment]
    controller._activate_push_to_talk()
    return controller


def test_settings_are_saved_to_file(controller: gui.Controller) -> None:
    new = replace(Config(), sound=False, microphone="Headset (USB)")

    controller.apply_settings(Settings(new, autostart=False))

    assert load_config(paths.config_file()) == new
    assert controller._recorder.microphone == "Headset (USB)"
    assert not controller.tray.sound_action.isChecked()


def test_autostart_is_switched(controller: gui.Controller) -> None:
    controller.apply_settings(Settings(Config(), autostart=True))

    assert autostart.is_enabled()


def test_hotkey_change_rebuilds_push_to_talk(controller: gui.Controller) -> None:
    old_target = controller._key_target

    controller.apply_settings(Settings(replace(Config(), hotkey="f9"), autostart=False))

    assert controller._key_target is not old_target
    assert controller._key_target._combo == frozenset({"f9"})  # type: ignore[union-attr]
    assert controller.tray._hotkey_label == "F9"


def test_language_change_does_not_reload_model(controller: gui.Controller) -> None:
    controller.apply_settings(Settings(replace(Config(), language="en"), autostart=False))

    assert controller._app.languages == ["en"]  # type: ignore[union-attr]
    assert controller.loads == []  # type: ignore[attr-defined]


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
