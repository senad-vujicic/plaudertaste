"""Einstellungsfenster: Änderungen gelten erst mit "Speichern"."""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from plaudertaste.catalog import AUTO, MODELS, format_size, language_options, model_label
from plaudertaste.config import Config
from plaudertaste.hotkey import describe_hotkey, hotkey_problem

AUTO_MODEL_LABEL = "Automatisch – large-v3-turbo mit NVIDIA-GPU, sonst small"
DEFAULT_MICROPHONE_LABEL = "Windows-Standard"
WAITING_TEXT = "Taste(n) drücken und loslassen …"


@dataclass(frozen=True)
class Settings:
    config: Config
    autostart: bool


class HotkeyButton(QPushButton):
    """Zeigt den Hotkey. Nach einem Klick wartet es auf eine neue Tastenkombination.

    Die Erkennung selbst übernimmt der globale Tastatur-Listener (er unterscheidet linke und
    rechte Strg). Solange gewartet wird, schnappt sich der Knopf die Tastatur, damit Qt
    Tasten wie Enter oder Esc nicht als "Speichern"/"Abbrechen" deutet.
    """

    def __init__(self, hotkey: str) -> None:
        super().__init__()
        self.hotkey = hotkey
        self.waiting = False
        self.setText(describe_hotkey(hotkey))

    def start_waiting(self) -> None:
        self.waiting = True
        self.setText(WAITING_TEXT)
        self.grabKeyboard()

    def finish_waiting(self, hotkey: str) -> None:
        self.waiting = False
        self.releaseKeyboard()
        self.hotkey = hotkey
        self.setText(describe_hotkey(hotkey))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.waiting:
            event.accept()  # schlucken – der globale Listener wertet aus
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if self.waiting:
            event.accept()
        else:
            super().keyReleaseEvent(event)


class SettingsDialog(QDialog):
    capture_requested = Signal()  # Controller soll die nächste Tastenkombination liefern

    def __init__(
        self,
        config: Config,
        autostart: bool,
        microphones: list[str],
        downloaded_models: set[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Plaudertaste – Einstellungen")
        self._config = config
        self._downloaded = downloaded_models

        self.hotkey_button = HotkeyButton(config.hotkey)
        self.hotkey_button.clicked.connect(self._on_hotkey_clicked)
        self.hotkey_hint = _hint_label()

        self.model_box = QComboBox()
        self.model_box.addItem(AUTO_MODEL_LABEL, AUTO)
        for info in MODELS:
            self.model_box.addItem(model_label(info, info.name in downloaded_models), info.name)
        _select(self.model_box, config.model)
        self.model_hint = _hint_label()
        self.model_box.currentIndexChanged.connect(self._update_model_hint)

        self.language_box = QComboBox()
        for code, name in language_options():
            self.language_box.addItem(name, code)
        _select(self.language_box, config.language)

        self.microphone_box = QComboBox()
        self.microphone_box.addItem(DEFAULT_MICROPHONE_LABEL, "")
        for name in microphones:
            self.microphone_box.addItem(name, name)
        if config.microphone and config.microphone not in microphones:
            # gespeichertes Gerät gerade nicht angesteckt – nicht stillschweigend verwerfen
            self.microphone_box.addItem(f"{config.microphone} (nicht verbunden)", config.microphone)
        _select(self.microphone_box, config.microphone)

        self.sound_check = QCheckBox("Ton bei Start und Ende der Aufnahme")
        self.sound_check.setChecked(config.sound)
        self.overlay_check = QCheckBox("Overlay unten am Bildschirm anzeigen")
        self.overlay_check.setChecked(config.overlay)
        self.autostart_check = QCheckBox("Mit Windows starten")
        self.autostart_check.setChecked(autostart)

        form = QFormLayout()
        form.addRow("Hotkey (halten zum Sprechen)", self.hotkey_button)
        form.addRow("", self.hotkey_hint)
        form.addRow("Modell", self.model_box)
        form.addRow("", self.model_hint)
        form.addRow("Sprache", self.language_box)
        form.addRow("Mikrofon", self.microphone_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Speichern")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addSpacing(8)
        for check in (self.sound_check, self.overlay_check, self.autostart_check):
            layout.addWidget(check)
        layout.addSpacing(8)
        layout.addWidget(buttons)
        self.setMinimumWidth(520)
        self._update_model_hint()

    def settings(self) -> Settings:
        config = replace(
            self._config,
            hotkey=self.hotkey_button.hotkey,
            model=self.model_box.currentData(),
            language=self.language_box.currentData(),
            microphone=self.microphone_box.currentData(),
            sound=self.sound_check.isChecked(),
            overlay=self.overlay_check.isChecked(),
        )
        return Settings(config=config, autostart=self.autostart_check.isChecked())

    def set_captured_hotkey(self, hotkey: str) -> None:
        """Vom Controller aufgerufen, sobald eine Tastenkombination losgelassen wurde."""
        problem = hotkey_problem(hotkey)
        if problem:
            self.hotkey_button.finish_waiting(self.hotkey_button.hotkey)  # alten behalten
            self.hotkey_hint.setText(problem)
        else:
            self.hotkey_button.finish_waiting(hotkey)
            self.hotkey_hint.setText("")
        self.hotkey_hint.setVisible(bool(self.hotkey_hint.text()))

    def _on_hotkey_clicked(self) -> None:
        if self.hotkey_button.waiting:
            return
        self.hotkey_hint.setText("")
        self.hotkey_hint.setVisible(False)
        self.hotkey_button.start_waiting()
        self.capture_requested.emit()

    def _update_model_hint(self) -> None:
        name = self.model_box.currentData()
        info = next((m for m in MODELS if m.name == name), None)
        if info is not None and name not in self._downloaded:
            self.model_hint.setText(
                f"Wird beim Speichern heruntergeladen ({format_size(info.size_mb)})."
            )
        else:
            self.model_hint.setText("")
        self.model_hint.setVisible(bool(self.model_hint.text()))

    def done(self, result: int) -> None:
        if self.hotkey_button.waiting:
            self.hotkey_button.releaseKeyboard()
        super().done(result)


def _hint_label() -> QLabel:
    label = QLabel()
    label.setWordWrap(True)
    label.setStyleSheet("color: #b26a00;")  # dunkles Orange: Hinweis, kein Fehler
    label.setVisible(False)
    return label


def _select(box: QComboBox, value: str) -> None:
    index = box.findData(value)
    box.setCurrentIndex(index if index >= 0 else 0)
