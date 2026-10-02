"""Einstellungs-Seite im Hauptfenster.

Änderungen gelten erst mit "Speichern". Speichern und Verwerfen sind nur aktiv, wenn sich
wirklich etwas geändert hat – so sieht man jederzeit, ob noch etwas ungespeichert ist.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from plaudertaste.catalog import AUTO, MODELS, format_size, language_options, model_label
from plaudertaste.config import Config
from plaudertaste.hotkey import describe_hotkey, hotkey_problem
from plaudertaste.ui import (
    SavedIndicator,
    ToggleSwitch,
    card,
    card_title,
    hint_label,
    page_title,
    set_hint,
)

AUTO_MODEL_LABEL = "Automatisch – large-v3-turbo mit NVIDIA-GPU, sonst small"
DEFAULT_MICROPHONE_LABEL = "Windows-Standard"
WAITING_TEXT = "Taste(n) drücken und loslassen …"
LABEL_WIDTH = 210  # gleiche Breite in allen Karten, damit die Felder bündig stehen


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
        self._saved = Settings(Config(), autostart=False)
        self._downloaded: set[str] = set()

        self.hotkey_button = HotkeyButton()
        self.hotkey_button.clicked.connect(self._on_hotkey_clicked)
        self.hotkey_hint = hint_label()
        self.model_box = QComboBox()
        self.model_hint = hint_label()
        self.language_box = QComboBox()
        for code, name in language_options():
            self.language_box.addItem(name, code)
        self.microphone_box = QComboBox()
        self.sound_check = ToggleSwitch("Ton bei Start und Ende der Aufnahme")
        self.overlay_check = ToggleSwitch("Overlay unten am Bildschirm anzeigen")
        self.autostart_check = ToggleSwitch("Mit Windows starten (still im Infobereich)")

        dictation = _form(
            ("Hotkey (halten zum Sprechen)", _with_hint(self.hotkey_button, self.hotkey_hint)),
            ("Sprache", self.language_box),
        )
        recognition = _form(
            ("Modell", _with_hint(self.model_box, self.model_hint)),
            ("Mikrofon", self.microphone_box),
        )

        self.saved_label = SavedIndicator()

        self.discard_button = QPushButton("Verwerfen")
        self.discard_button.clicked.connect(self.reset)
        self.save_button = QPushButton("Speichern")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(lambda: self.save_requested.emit(self.settings()))
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.saved_label)
        buttons.addSpacing(12)
        buttons.addWidget(self.discard_button)
        buttons.addWidget(self.save_button)

        for box in (self.model_box, self.language_box, self.microphone_box):
            # nicht so breit wie der längste Eintrag werden – lange Einträge werden gekürzt
            box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            box.setMinimumContentsLength(20)

        # Nur die Karten scrollen – Speichern/Verwerfen bleiben immer sichtbar.
        content = QWidget()
        cards = QVBoxLayout(content)
        cards.setContentsMargins(0, 0, 8, 0)  # Platz für die Scrollleiste
        cards.setSpacing(14)
        cards.addWidget(card(card_title("Diktat"), dictation))
        cards.addWidget(card(card_title("Erkennung"), recognition))
        cards.addWidget(
            card(card_title("Verhalten"), self.sound_check, self.overlay_check, self.autostart_check)
        )
        cards.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(page_title("Einstellungen"))
        layout.addWidget(scroll, 1)
        layout.addLayout(buttons)

        self.model_box.currentIndexChanged.connect(self._update_model_hint)
        for box in (self.model_box, self.language_box, self.microphone_box):
            box.currentIndexChanged.connect(self._on_changed)
        for switch in (self.sound_check, self.overlay_check, self.autostart_check):
            switch.toggled.connect(self._on_changed)
        self._on_changed()

    def load(
        self, config: Config, autostart: bool, microphones: list[str], downloaded_models: set[str]
    ) -> None:
        """Zeigt den gespeicherten Stand – mit frischer Mikrofonliste und Download-Status."""
        self._saved = Settings(config, autostart)
        self._downloaded = downloaded_models

        self.model_box.blockSignals(True)
        self.model_box.clear()
        self.model_box.addItem(AUTO_MODEL_LABEL, AUTO)
        for info in MODELS:
            self.model_box.addItem(model_label(info, info.name in downloaded_models), info.name)
        self.model_box.blockSignals(False)

        self.microphone_box.blockSignals(True)
        self.microphone_box.clear()
        self.microphone_box.addItem(DEFAULT_MICROPHONE_LABEL, "")
        for name in microphones:
            self.microphone_box.addItem(name, name)
        if config.microphone and config.microphone not in microphones:
            # gespeichertes Gerät gerade nicht angesteckt – nicht stillschweigend verwerfen
            self.microphone_box.addItem(f"{config.microphone} (nicht verbunden)", config.microphone)
        self.microphone_box.blockSignals(False)
        self.reset()

    def reset(self) -> None:
        """Alle Felder auf den gespeicherten Stand zurücksetzen ("Verwerfen")."""
        self.cancel_capture()
        config = self._saved.config
        self.hotkey_button.show_hotkey(config.hotkey)
        set_hint(self.hotkey_hint, "")
        _select(self.model_box, config.model)
        _select(self.language_box, config.language)
        _select(self.microphone_box, config.microphone)
        self.sound_check.setChecked(config.sound)
        self.overlay_check.setChecked(config.overlay)
        self.autostart_check.setChecked(self._saved.autostart)
        self._update_model_hint()
        self._on_changed()

    def settings(self) -> Settings:
        config = replace(
            self._saved.config,
            hotkey=self.hotkey_button.hotkey,
            model=self.model_box.currentData(),
            language=self.language_box.currentData(),
            microphone=self.microphone_box.currentData(),
            sound=self.sound_check.isChecked(),
            overlay=self.overlay_check.isChecked(),
        )
        return Settings(config=config, autostart=self.autostart_check.isChecked())

    def has_changes(self) -> bool:
        return self.settings() != self._saved

    def show_saved(self) -> None:
        """Bestätigung nach erfolgreichem Speichern: grün einblenden, dann verblassen."""
        self.saved_label.flash()

    def set_captured_hotkey(self, hotkey: str) -> None:
        """Vom Controller aufgerufen, sobald eine Tastenkombination losgelassen wurde."""
        if not self.hotkey_button.waiting:
            return
        problem = hotkey_problem(hotkey)
        self.hotkey_button.show_hotkey(self.hotkey_button.hotkey if problem else hotkey)
        set_hint(self.hotkey_hint, problem or "")
        self._on_changed()

    def cancel_capture(self) -> None:
        """Hotkey-Aufnahme abbrechen, z. B. wenn die Seite gewechselt wird."""
        if self.hotkey_button.waiting:
            self.hotkey_button.show_hotkey(self.hotkey_button.hotkey)
            self.capture_cancelled.emit()

    def _on_changed(self) -> None:
        changed = self.has_changes()
        self.save_button.setEnabled(changed)
        self.discard_button.setEnabled(changed)
        if changed:  # eine alte Bestätigung passt nicht mehr zum aktuellen Stand
            self.saved_label.clear()

    def _on_hotkey_clicked(self) -> None:
        if self.hotkey_button.waiting:
            return
        set_hint(self.hotkey_hint, "")
        self.hotkey_button.start_waiting()
        self.capture_requested.emit()

    def _update_model_hint(self) -> None:
        name = self.model_box.currentData()
        info = next((m for m in MODELS if m.name == name), None)
        text = ""
        if info is not None and name not in self._downloaded:
            text = f"Wird beim Speichern heruntergeladen ({format_size(info.size_mb)})."
        set_hint(self.model_hint, text)


def _with_hint(field: QWidget, hint: QLabel) -> QWidget:
    """Feld mit Hinweis direkt darunter – ohne leere Zeile, solange der Hinweis leer ist."""
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(field)
    layout.addWidget(hint)
    return box


def _form(*rows: tuple[str, QWidget]) -> QFormLayout:
    form = QFormLayout()
    form.setVerticalSpacing(10)
    for text, field in rows:
        label = QLabel(text)
        label.setFixedWidth(LABEL_WIDTH)
        form.addRow(label, field)
    return form


def _select(box: QComboBox, value: str) -> None:
    index = box.findData(value)
    box.setCurrentIndex(index if index >= 0 else 0)
