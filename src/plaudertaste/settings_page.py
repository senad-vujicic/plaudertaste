"""Einstellungs-Seite im Hauptfenster: Änderungen gelten erst mit "Speichern"."""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from plaudertaste.catalog import AUTO, MODELS, format_size, language_options, model_label
from plaudertaste.config import Config
from plaudertaste.hotkey import describe_hotkey, hotkey_problem
from plaudertaste.ui import page_title

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
    Tasten wie Enter oder Leertaste nicht als Klick auf einen Knopf deutet.
    """

    def __init__(self) -> None:
        super().__init__()
        self.hotkey = ""
        self.waiting = False

    def show_hotkey(self, hotkey: str) -> None:
        if self.waiting:
            self.waiting = False
            self.releaseKeyboard()
        self.hotkey = hotkey
        self.setText(describe_hotkey(hotkey))

    def start_waiting(self) -> None:
        self.waiting = True
        self.setText(WAITING_TEXT)
        self.grabKeyboard()

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


class SettingsPage(QWidget):
    save_requested = Signal(object)  # Settings
    capture_requested = Signal()  # Controller soll die nächste Tastenkombination liefern
    capture_cancelled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._config = Config()
        self._autostart = False
        self._downloaded: set[str] = set()

        self.hotkey_button = HotkeyButton()
        self.hotkey_button.clicked.connect(self._on_hotkey_clicked)
        self.hotkey_hint = _hint_label()
        self.model_box = QComboBox()
        self.model_box.currentIndexChanged.connect(self._update_model_hint)
        self.model_hint = _hint_label()
        self.language_box = QComboBox()
        for code, name in language_options():
            self.language_box.addItem(name, code)
        self.microphone_box = QComboBox()
        self.sound_check = QCheckBox("Ton bei Start und Ende der Aufnahme")
        self.overlay_check = QCheckBox("Overlay unten am Bildschirm anzeigen")
        self.autostart_check = QCheckBox("Mit Windows starten (still im Infobereich)")

        form = QFormLayout()
        form.addRow("Hotkey (halten zum Sprechen)", self.hotkey_button)
        form.addRow("", self.hotkey_hint)
        form.addRow("Modell", self.model_box)
        form.addRow("", self.model_hint)
        form.addRow("Sprache", self.language_box)
        form.addRow("Mikrofon", self.microphone_box)

        self.discard_button = QPushButton("Verwerfen")
        self.discard_button.clicked.connect(self.reset)
        self.save_button = QPushButton("Speichern")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(lambda: self.save_requested.emit(self.settings()))
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.discard_button)
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.addWidget(page_title("Einstellungen"))
        layout.addLayout(form)
        layout.addSpacing(8)
        for check in (self.sound_check, self.overlay_check, self.autostart_check):
            layout.addWidget(check)
        layout.addStretch()
        layout.addLayout(buttons)

    def load(
        self, config: Config, autostart: bool, microphones: list[str], downloaded_models: set[str]
    ) -> None:
        """Zeigt den gespeicherten Stand – mit frischer Mikrofonliste und Download-Status."""
        self._config = config
        self._autostart = autostart
        self._downloaded = downloaded_models

        self.model_box.blockSignals(True)
        self.model_box.clear()
        self.model_box.addItem(AUTO_MODEL_LABEL, AUTO)
        for info in MODELS:
            self.model_box.addItem(model_label(info, info.name in downloaded_models), info.name)
        self.model_box.blockSignals(False)

        self.microphone_box.clear()
        self.microphone_box.addItem(DEFAULT_MICROPHONE_LABEL, "")
        for name in microphones:
            self.microphone_box.addItem(name, name)
        if config.microphone and config.microphone not in microphones:
            # gespeichertes Gerät gerade nicht angesteckt – nicht stillschweigend verwerfen
            self.microphone_box.addItem(f"{config.microphone} (nicht verbunden)", config.microphone)
        self.reset()

    def reset(self) -> None:
        """Alle Felder auf den gespeicherten Stand zurücksetzen ("Verwerfen")."""
        self.cancel_capture()
        config = self._config
        self.hotkey_button.show_hotkey(config.hotkey)
        _set_hint(self.hotkey_hint, "")
        _select(self.model_box, config.model)
        _select(self.language_box, config.language)
        _select(self.microphone_box, config.microphone)
        self.sound_check.setChecked(config.sound)
        self.overlay_check.setChecked(config.overlay)
        self.autostart_check.setChecked(self._autostart)
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
        if not self.hotkey_button.waiting:
            return
        problem = hotkey_problem(hotkey)
        if problem:
            self.hotkey_button.show_hotkey(self.hotkey_button.hotkey)  # alten behalten
        else:
            self.hotkey_button.show_hotkey(hotkey)
        _set_hint(self.hotkey_hint, problem or "")

    def cancel_capture(self) -> None:
        """Hotkey-Aufnahme abbrechen, z. B. wenn die Seite gewechselt wird."""
        if self.hotkey_button.waiting:
            self.hotkey_button.show_hotkey(self.hotkey_button.hotkey)
            self.capture_cancelled.emit()

    def _on_hotkey_clicked(self) -> None:
        if self.hotkey_button.waiting:
            return
        _set_hint(self.hotkey_hint, "")
        self.hotkey_button.start_waiting()
        self.capture_requested.emit()

    def _update_model_hint(self) -> None:
        name = self.model_box.currentData()
        info = next((m for m in MODELS if m.name == name), None)
        text = ""
        if info is not None and name not in self._downloaded:
            text = f"Wird beim Speichern heruntergeladen ({format_size(info.size_mb)})."
        _set_hint(self.model_hint, text)


def _hint_label() -> QLabel:
    label = QLabel()
    label.setWordWrap(True)
    label.setStyleSheet("color: #b26a00;")  # dunkles Orange: Hinweis, kein Fehler
    label.setVisible(False)
    return label


def _set_hint(label: QLabel, text: str) -> None:
    label.setText(text)
    label.setVisible(bool(text))


def _select(box: QComboBox, value: str) -> None:
    index = box.findData(value)
    box.setCurrentIndex(index if index >= 0 else 0)
