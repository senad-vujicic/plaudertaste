from collections.abc import Iterator

import pytest
from PySide6.QtGui import QIcon

from plaudertaste.config import Config
from plaudertaste.recorder import RecorderError
from plaudertaste.settings_page import Settings
from plaudertaste.setup_wizard import SetupWizard

pytestmark = pytest.mark.usefixtures("qapp")


class FakeRecorder:
    """Merkt sich, wann das Mikrofon offen ist – ohne echtes Gerät."""

    open_count = 0
    fail = False

    def __init__(self, microphone: str = "") -> None:
        self.microphone = microphone
        self.level = 0.05

    def start(self) -> None:
        if FakeRecorder.fail:
            raise RecorderError("Kein Mikrofon verfügbar.")
        FakeRecorder.open_count += 1

    def stop(self) -> None:
        FakeRecorder.open_count -= 1


@pytest.fixture
def wizard() -> Iterator[SetupWizard]:
    FakeRecorder.open_count, FakeRecorder.fail = 0, False
    wizard = SetupWizard(QIcon(), Config(), False, ["Volt 2"], recorder_factory=FakeRecorder)  # type: ignore[arg-type]
    yield wizard
    wizard.deleteLater()


def collect(wizard: SetupWizard) -> list[Settings]:
    changes: list[Settings] = []
    wizard.settings_changed.connect(changes.append)
    return changes


def test_navigation_through_all_steps(wizard: SetupWizard) -> None:
    assert wizard.step == wizard.WELCOME
    assert not wizard.back_button.isEnabled()  # erste Seite

    for _ in range(wizard.DONE):
        wizard.next_button.click()

    assert wizard.step == wizard.DONE
    assert wizard.next_button.text() == "Los geht's"
    assert wizard.skip_button.isHidden()


def test_microphone_is_only_open_on_its_page(wizard: SetupWizard) -> None:
    wizard.next_button.click()  # -> Mikrofon
    assert FakeRecorder.open_count == 1
    wizard._update_level()
    assert wizard.level_bar.value() > 0  # Pegel kommt an

    wizard.next_button.click()  # -> Hotkey
    assert FakeRecorder.open_count == 0  # sofort wieder geschlossen


def test_missing_microphone_shows_hint(wizard: SetupWizard) -> None:
    FakeRecorder.fail = True

    wizard.next_button.click()

    assert "Kein Mikrofon" in wizard.mic_hint.text()


def test_microphone_choice_applies_immediately(wizard: SetupWizard) -> None:
    changes = collect(wizard)
    wizard.next_button.click()

    wizard.microphone_box.setCurrentIndex(wizard.microphone_box.findData("Volt 2"))

    assert changes[-1].config.microphone == "Volt 2"
    assert FakeRecorder.open_count == 1  # Test läuft mit dem neuen Gerät weiter


def test_hotkey_capture(wizard: SetupWizard) -> None:
    changes = collect(wizard)
    requests: list[bool] = []
    wizard.capture_requested.connect(lambda: requests.append(True))
    wizard._go(wizard.HOTKEY)

    wizard.hotkey_button.click()
    wizard.set_captured_hotkey("a")  # Schreibtaste -> abgelehnt
    assert "beim Schreiben gebraucht" in wizard.hotkey_hint.text()
    wizard.hotkey_button.click()
    wizard.set_captured_hotkey("f9")

    assert requests == [True, True]
    assert changes[-1].config.hotkey == "f9"
    assert wizard.hotkey_button.text() == "F9"


def test_probe_comes_after_options_and_before_done(wizard: SetupWizard) -> None:
    assert wizard.MODEL < wizard.OPTIONS < wizard.PROBE == wizard.DONE - 1


def test_probe_waits_for_model_with_progress(wizard: SetupWizard) -> None:
    wizard.show_model_progress("large-v3-turbo", 45)
    wizard._go(wizard.PROBE)

    assert not wizard.probe_field.isEnabled()  # ausgegraut – nicht "kaputt"
    assert "noch geladen (45 %)" in wizard.probe_instruction.text()
    assert wizard.probe_bar.value() == 45

    wizard.show_model_ready("large-v3-turbo auf der Grafikkarte (schnell)")

    assert wizard.probe_field.isEnabled()
    assert "Jetzt ausprobieren" in wizard.probe_instruction.text()
    assert wizard.probe_bar.isHidden()


def test_probe_uses_chosen_hotkey_and_confirms(wizard: SetupWizard) -> None:
    wizard._apply(Config(hotkey="f9"))
    wizard.show_model_ready("small auf dem Prozessor")
    wizard._go(wizard.PROBE)
    assert "<b>F9</b>" in wizard.probe_instruction.text()

    wizard.probe_field.setPlainText("Hallo Welt")

    assert "Klappt" in wizard.probe_result.text()


def test_options_are_applied_when_leaving(wizard: SetupWizard) -> None:
    changes = collect(wizard)
    wizard._go(wizard.OPTIONS)
    wizard.autostart_check.setChecked(True)
    wizard.sound_check.setChecked(False)

    wizard.next_button.click()

    assert changes[-1].autostart is True
    assert changes[-1].config.sound is False


def test_model_status_texts(wizard: SetupWizard) -> None:
    wizard.show_model_progress("large-v3-turbo", 42)
    assert "42 %" in wizard.model_label.text()
    assert wizard.model_bar.value() == 42

    wizard.show_model_ready("large-v3-turbo auf der Grafikkarte (schnell)")
    assert "Bereit" in wizard.model_label.text()


def test_skip_finishes_once_and_closes_microphone(wizard: SetupWizard) -> None:
    finished: list[bool] = []
    wizard.finished_setup.connect(lambda: finished.append(True))
    wizard.next_button.click()  # Mikrofon offen

    wizard.skip_button.click()
    wizard.reject()  # z. B. zusätzlich Esc – darf nicht doppelt melden
    wizard.close()

    assert finished == [True]
    assert FakeRecorder.open_count == 0


def test_back_from_last_page(wizard: SetupWizard) -> None:
    wizard._go(wizard.DONE)

    wizard.back_button.click()

    assert wizard.step == wizard.PROBE
