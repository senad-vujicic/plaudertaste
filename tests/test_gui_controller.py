from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from plaudertaste import autostart, gui, paths
from plaudertaste.config import Config, load_config
from plaudertaste.hotkey import HotkeyCapture
from plaudertaste.main_window import Page
from plaudertaste.network import NetworkGuard
from plaudertaste.settings_page import Settings
from plaudertaste.sounds import TonePlayer


class FakeApp:
    def __init__(self) -> None:
        self.languages: list[str | None] = []
        self.dictionaries: list[object] = []

    def set_dictionary(self, dictionary: object) -> None:
        self.dictionaries.append(dictionary)

    def set_language(self, language: str | None) -> None:
        self.languages.append(language)

    def on_start(self) -> None: ...
    def on_stop(self) -> None: ...
    def on_cancel(self) -> None: ...
    def on_undo(self) -> None: ...
    def forget_last_dictation(self) -> None: ...


@pytest.fixture
def controller(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[gui.Controller]:
    # Nichts Echtes anfassen: Config, Statistik, Registry, Mikrofone, Modell-Cache.
    monkeypatch.setattr(paths, "config_file", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(paths, "stats_file", lambda: tmp_path / "stats.json")
    monkeypatch.setattr(paths, "dictionary_file", lambda: tmp_path / "woerterbuch.toml")
    registry = {"enabled": False}
    monkeypatch.setattr(autostart, "is_enabled", lambda: registry["enabled"])
    monkeypatch.setattr(autostart, "set_enabled", lambda value: registry.update(enabled=value))
    monkeypatch.setattr(gui, "list_microphones", lambda: ["Headset (USB)"])
    monkeypatch.setattr(gui, "is_model_downloaded", lambda name: name == "small")
    # Eigener Netzwerk-Wächter pro Test: Anmeldungen gelöschter Controller bleiben nicht hängen.
    monkeypatch.setattr(gui, "guard", NetworkGuard())

    controller = gui.Controller(Config(), tmp_path / "app.log")
    controller._tones = TonePlayer(enabled=True, play=lambda tone: None)  # Tests bleiben stumm
    controller.loads: list[Config] = []  # type: ignore[attr-defined]
    monkeypatch.setattr(
        controller,
        "_load_model_in_background",
        lambda: controller.loads.append(controller._config),  # type: ignore[attr-defined]
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

    controller._on_model_failed("Download fehlgeschlagen.", "ConnectError")

    assert controller._config.model == "auto"
    assert load_config(paths.config_file()).model == "auto"


def test_hotkey_capture_pauses_dictation(controller: gui.Controller) -> None:
    push_to_talk = controller._key_target

    controller._start_hotkey_capture(controller.settings_page)
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
    assert controller.window.start_page.last_text.text() == "Hallo liebe Welt"
    assert controller.window.start_page.last_copy_button.isEnabled()


def test_closing_window_hides_it_and_hints_once(
    controller: gui.Controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[str] = []
    monkeypatch.setattr(
        controller.tray, "showMessage", lambda title, text, *rest: messages.append(text)
    )
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


def test_download_progress_shows_banner_also_for_large_models(
    controller: gui.Controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Über 2^31 Bytes: würde mit einem 32-Bit-Qt-int überlaufen.
    controller._loader.progress.emit("large-v3", 1_545_500_000, 3_091_000_000)

    banner = controller.window.download_banner
    assert not banner.isHidden()
    assert banner.bar.value() == 50
    assert "1.545 von 3.091 MB" in banner.text.text()
    assert "50 %" in controller.tray.toolTip()

    monkeypatch.setattr(gui.QMessageBox, "warning", lambda *args: None)
    controller._on_model_failed("Download fehlgeschlagen.", "ConnectError")  # Download scheitert
    assert banner.isHidden()


def test_cancelled_model_change_keeps_old_model_and_display(controller: gui.Controller) -> None:
    controller._model_text = "large-v3-turbo · GPU"
    controller.apply_settings(Settings(replace(Config(), model="medium"), autostart=False))
    assert controller.window.start_page.model_label.text() == "wird geladen …"

    controller.cancel_download()
    assert controller._loader.cancel_requested
    controller._on_model_cancelled()  # meldet der Lade-Thread, sobald der Prozess beendet ist

    assert controller._config.model == "auto"
    assert load_config(paths.config_file()).model == "auto"
    assert controller.window.start_page.model_label.text() == "large-v3-turbo · GPU"
    assert controller.window.download_banner.isHidden()


def test_failed_model_change_restores_model_display(
    controller: gui.Controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gui.QMessageBox, "warning", lambda *args: None)
    controller._model_text = "large-v3-turbo · GPU"
    controller.apply_settings(Settings(replace(Config(), model="medium"), autostart=False))

    controller._on_model_failed("Download fehlgeschlagen.", "ConnectError")

    assert controller.window.start_page.model_label.text() == "large-v3-turbo · GPU"


@pytest.mark.parametrize(("answer", "cancelled"), [("Yes", True), ("No", False)])
def test_cancel_on_first_start_asks_first(
    controller: gui.Controller, monkeypatch: pytest.MonkeyPatch, answer: str, cancelled: bool
) -> None:
    controller._app = None  # erster Start: noch kein Modell geladen
    button = getattr(gui.QMessageBox.StandardButton, answer)
    monkeypatch.setattr(gui.QMessageBox, "question", lambda *args: button)

    controller.cancel_download()

    assert controller._loader.cancel_requested is cancelled


def test_serious_notice_goes_to_overlay_tray_and_start_page(
    controller: gui.Controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    from plaudertaste.app import MIC_UNAVAILABLE

    tray_messages: list[str] = []
    monkeypatch.setattr(
        controller.tray, "showMessage", lambda title, text, *rest: tray_messages.append(text)
    )

    controller._on_notice(MIC_UNAVAILABLE)

    assert controller._overlay.message == MIC_UNAVAILABLE.text
    assert tray_messages == [MIC_UNAVAILABLE.text]
    assert not controller.window.start_page.problems_card.isHidden()
    assert "Kein Mikrofon" in controller.window.start_page.problems_label.text()

    controller._on_status(gui.Status.RECORDING)  # Mikrofon klappt wieder
    assert controller.window.start_page.problems_card.isHidden()
    controller._on_status(gui.Status.READY)


def test_minor_notice_only_in_overlay(
    controller: gui.Controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    from plaudertaste.app import NOTHING_UNDERSTOOD

    tray_messages: list[str] = []
    monkeypatch.setattr(
        controller.tray, "showMessage", lambda title, text, *rest: tray_messages.append(text)
    )

    controller._on_notice(NOTHING_UNDERSTOOD)

    assert controller._overlay.message == NOTHING_UNDERSTOOD.text
    assert tray_messages == []
    assert controller.window.start_page.problems_card.isHidden()


def test_missing_microphone_shows_problem_once(
    controller: gui.Controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    tray_messages: list[str] = []
    monkeypatch.setattr(
        controller.tray, "showMessage", lambda title, text, *rest: tray_messages.append(text)
    )
    controller._config = replace(controller._config, microphone="Headset (USB)")
    controller._recorder.fell_back_to_default = True

    for _ in range(3):  # drei Aufnahmen hintereinander
        controller._on_status(gui.Status.RECORDING)
        controller._on_status(gui.Status.READY)

    assert "Headset (USB)" in controller.window.start_page.problems_label.text()
    assert len(tray_messages) == 1  # nur beim ersten Mal benachrichtigen


def test_gpu_fallback_is_shown_on_start_page(controller: gui.Controller) -> None:
    controller._set_problem("gpu", gui.PROBLEM_GPU_FALLBACK)

    assert "Grafikkarte" in controller.window.start_page.problems_label.text()


def test_key_error_does_not_kill_listener(controller: gui.Controller) -> None:
    class Broken:
        def press(self, key: str) -> None:
            raise RuntimeError("Audio-Treiber weg")

        def release(self, key: str) -> None:
            raise RuntimeError("Audio-Treiber weg")

    controller._key_target = Broken()  # type: ignore[assignment]

    controller._on_key_press("ctrl_r")  # darf keine Ausnahme nach außen werfen
    controller._on_key_release("ctrl_r")


def test_dictionary_changes_are_saved_and_applied_immediately(controller: gui.Controller) -> None:
    from plaudertaste.dictionary import Dictionary, load_dictionary

    page = controller.dictionary_page
    page.term_input.setText("Plaudertaste")
    page.term_input.returnPressed.emit()

    expected = Dictionary(terms=("Plaudertaste",))
    assert load_dictionary(paths.dictionary_file()) == expected
    assert controller._app.dictionaries == [expected]  # type: ignore[union-attr]
    assert not page.saved_label.isHidden()


def test_broken_dictionary_file_is_kept_as_backup(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths, "config_file", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(paths, "stats_file", lambda: tmp_path / "stats.json")
    monkeypatch.setattr(paths, "dictionary_file", lambda: tmp_path / "woerterbuch.toml")
    monkeypatch.setattr(gui.QSystemTrayIcon, "showMessage", lambda *args: None)
    monkeypatch.setattr(gui, "guard", NetworkGuard())
    (tmp_path / "woerterbuch.toml").write_text("terms = [kaputt", encoding="utf-8")

    controller = gui.Controller(Config(), tmp_path / "app.log")

    assert (tmp_path / "woerterbuch.defekt.toml").read_text(encoding="utf-8") == "terms = [kaputt"
    assert "Wörterbuch-Datei fehlerhaft" in controller.window.start_page.problems_label.text()
    controller.window.deleteLater()


def test_voice_commands_setting_reaches_running_app(controller: gui.Controller) -> None:
    controller.apply_settings(
        Settings(replace(Config(), voice_commands=False, remove_fillers=False), autostart=False)
    )

    assert controller._app.voice_commands is False  # type: ignore[union-attr]
    assert controller._app.remove_fillers is False  # type: ignore[union-attr]


def test_backspace_is_swallowed_only_while_hotkey_held(controller: gui.Controller) -> None:
    controller._on_key_press("ctrl_r")
    assert controller._swallow("backspace")
    assert not controller._swallow("a")
    controller._on_key_release("ctrl_r")

    assert not controller._swallow("backspace")


def test_forgotten_hands_free_is_stopped(controller: gui.Controller) -> None:
    for _ in range(2):  # zweimal schnell tippen
        controller._on_key_press("ctrl_r")
        controller._on_key_release("ctrl_r")
    assert controller._push_to_talk.is_hands_free  # type: ignore[union-attr]
    assert controller._hands_free_timer.isActive()

    controller._stop_forgotten_hands_free()  # was der Timer nach 5 Minuten auslöst

    assert not controller._push_to_talk.is_recording  # type: ignore[union-attr]


def test_update_is_shown_on_start_page(
    controller: gui.Controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    from plaudertaste.updates import Update

    monkeypatch.setattr(controller.tray, "showMessage", lambda *args: None)

    controller._on_update_available(
        Update("0.2.0", "https://github.com/senad-vujicic/plaudertaste/releases/tag/v0.2.0")
    )

    page = controller.window.start_page
    assert not page.update_card.isHidden()
    assert "0.2.0" in page.update_label.text()


def test_offline_setting_switches_guard(controller: gui.Controller) -> None:
    controller.apply_settings(Settings(replace(Config(), offline_mode=True), autostart=False))
    assert gui.guard.offline is True

    controller.apply_settings(Settings(Config(), autostart=False))
    assert gui.guard.offline is False


def test_connections_appear_in_settings(controller: gui.Controller) -> None:
    gui.guard.record("api.github.com")  # wie beim echten Update-Check

    label = controller.settings_page.network_label.text()
    assert "api.github.com · Update-Prüfung" in label


def test_model_switch_does_not_abort_hotkey_capture(controller: gui.Controller) -> None:
    controller._start_hotkey_capture(controller.settings_page)

    controller._activate_push_to_talk()  # z. B. weil gerade ein neues Modell fertig ist

    assert isinstance(controller._key_target, HotkeyCapture)
    controller._on_hotkey_captured("f9")
    assert controller._key_target is controller._push_to_talk


def test_first_start_opens_wizard_and_routes_hotkey_to_it(
    controller: gui.Controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gui, "list_microphones", lambda: [])
    controller._open_setup_wizard()
    wizard = controller.wizard
    assert wizard is not None

    wizard._go(wizard.HOTKEY)
    wizard.hotkey_button.click()  # Assistent "bestellt" eine Taste
    controller._on_key_press("f9")
    controller._on_key_release("f9")

    assert wizard.hotkey_button.hotkey == "f9"
    assert controller._config.hotkey == "f9"  # sofort übernommen

    wizard.skip_button.click()
    assert controller.wizard is None
    assert controller.window.isVisible()
