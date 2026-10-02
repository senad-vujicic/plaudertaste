"""Einrichtungsassistent für den allerersten Start.

Schritte: Willkommen → Mikrofon (mit Pegeltest) → Hotkey → Sprachmodell → Optionen →
Probe-Diktat → Fertig. Das Probe-Diktat steht am Ende und wartet sichtbar auf das
Sprachmodell, das im Hintergrund lädt – so wirkt nichts kaputt.

Änderungen wirken sofort (über `settings_changed`), damit das Probe-Diktat schon mit dem
gewählten Mikrofon und Hotkey funktioniert. "Überspringen" behält die Standardwerte.
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from plaudertaste.config import Config
from plaudertaste.hotkey import describe_hotkey, hotkey_problem
from plaudertaste.overlay import level_to_height
from plaudertaste.recorder import Recorder, RecorderError
from plaudertaste.settings_page import DEFAULT_MICROPHONE_LABEL, HotkeyButton, Settings
from plaudertaste.theme import ACCENT, SWITCH_OFF
from plaudertaste.ui import ToggleSwitch, card, hint_label, muted_label, page_title, set_hint

LEVEL_MS = 33  # Pegelanzeige ~30-mal pro Sekunde


class _Step(QWidget):
    def __init__(self, title: str, *items: QWidget) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(page_title(title))
        for item in items:
            layout.addWidget(item)
        layout.addStretch()


def _text(html: str) -> QLabel:
    label = QLabel(html)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    return label


class SetupWizard(QDialog):
    WELCOME, MICROPHONE, HOTKEY, MODEL, OPTIONS, PROBE, DONE = range(7)

    settings_changed = Signal(object)  # Settings – sofort anwenden
    capture_requested = Signal()  # Controller soll die nächste Tastenkombination liefern
    capture_cancelled = Signal()
    finished_setup = Signal()

    def __init__(
        self,
        icon: QIcon,
        config: Config,
        autostart: bool,
        microphones: list[str],
        recorder_factory: type[Recorder] = Recorder,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Plaudertaste – Einrichtung")
        self.setWindowIcon(icon)
        self.setMinimumSize(640, 520)
        self._settings = Settings(config, autostart)
        self._recorder_factory = recorder_factory
        self._mic_test: Recorder | None = None
        self._finished = False
        self._model_ready = False
        self._model_percent: int | None = None  # None = noch kein Fortschritt gemeldet

        # --- 1. Willkommen ---
        welcome = _Step(
            "Willkommen bei Plaudertaste",
            _text(
                "Mit Plaudertaste schreibst du in <b>jedem Programm</b> per Sprache: "
                "Taste gedrückt halten, sprechen, loslassen – der Text erscheint dort, wo "
                "dein Cursor steht."
            ),
            card(
                _text(
                    "<b>100 % lokal.</b> Deine Sprache und dein Text verlassen nie diesen "
                    "Rechner. Ins Internet geht Plaudertaste nur, um einmalig das Sprachmodell "
                    "herunterzuladen und nach Updates zu fragen."
                )
            ),
            muted_label("Die Einrichtung dauert etwa eine Minute."),
        )
        logo = QLabel()
        logo.setPixmap(icon.pixmap(72, 72))
        welcome.layout().insertWidget(0, logo)

        # --- 2. Mikrofon ---
        self.microphone_box = QComboBox()
        self.microphone_box.addItem(DEFAULT_MICROPHONE_LABEL, "")
        for name in microphones:
            self.microphone_box.addItem(name, name)
        index = self.microphone_box.findData(config.microphone)
        self.microphone_box.setCurrentIndex(max(index, 0))
        self.microphone_box.currentIndexChanged.connect(self._on_microphone_changed)
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.mic_hint = hint_label()
        microphone = _Step(
            "Mikrofon",
            muted_label("Wähle dein Mikrofon und sag etwas – der Balken sollte ausschlagen."),
            self.microphone_box,
            self.level_bar,
            self.mic_hint,
        )
        self._level_timer = QTimer(self, interval=LEVEL_MS)
        self._level_timer.timeout.connect(self._update_level)

        # --- 3. Hotkey ---
        self.hotkey_button = HotkeyButton()
        self.hotkey_button.show_hotkey(config.hotkey)
        self.hotkey_button.clicked.connect(self._on_hotkey_clicked)
        self.hotkey_hint = hint_label()
        hotkey = _Step(
            "Hotkey",
            _text(
                "Diese Taste hältst du zum Sprechen gedrückt. <b>Rechte Strg</b> wird beim "
                "Schreiben kaum gebraucht und ist deshalb ein guter Start. Zum Ändern "
                "auf den Knopf klicken und die gewünschte Taste drücken."
            ),
            self.hotkey_button,
            self.hotkey_hint,
        )

        # --- 4. Sprachmodell ---
        self.model_label = _text("Sprachmodell wird vorbereitet …")
        self.model_bar = QProgressBar()
        self.model_bar.setRange(0, 0)  # unbestimmt, bis Fortschritt kommt
        model = _Step(
            "Sprachmodell",
            muted_label(
                "Plaudertaste wählt automatisch das passende Modell für deinen Rechner und "
                "lädt es einmalig herunter. Du kannst währenddessen schon weitermachen."
            ),
            self.model_label,
            self.model_bar,
        )

        # --- 5. Optionen ---
        self.autostart_check = ToggleSwitch("Mit Windows starten (still im Infobereich)")
        self.sound_check = ToggleSwitch("Ton bei Start und Ende der Aufnahme")
        self.overlay_check = ToggleSwitch("Overlay unten am Bildschirm anzeigen")
        self.offline_check = ToggleSwitch(
            "Offline-Modus: danach jede Internetverbindung blockieren"
        )
        self.autostart_check.setChecked(autostart)
        self.sound_check.setChecked(config.sound)
        self.overlay_check.setChecked(config.overlay)
        self.offline_check.setChecked(config.offline_mode)
        options = _Step(
            "Optionen",
            self.autostart_check,
            self.sound_check,
            self.overlay_check,
            self.offline_check,
            muted_label(
                "Den Offline-Modus erst einschalten, wenn das Sprachmodell fertig "
                "heruntergeladen ist. Alles lässt sich später in den Einstellungen ändern."
            ),
        )

        # --- 6. Probe-Diktat (wartet, bis das Sprachmodell bereit ist) ---
        self.probe_instruction = _text("")
        self.probe_bar = QProgressBar()
        self.probe_bar.setRange(0, 0)
        self.probe_field = QPlainTextEdit()
        self.probe_field.setPlaceholderText("Hier erscheint dein Text …")
        self.probe_field.setEnabled(False)
        self.probe_field.textChanged.connect(self._on_probe_text)
        self.probe_result = QLabel()
        self.probe_result.setObjectName("success")
        probe = _Step(
            "Probe-Diktat",
            self.probe_instruction,
            self.probe_bar,
            self.probe_field,
            self.probe_result,
        )
        self._update_probe()

        # --- 7. Fertig ---
        self.summary = _text("")
        done = _Step("Fertig!", self.summary)

        self.pages = QStackedWidget()
        for step in (welcome, microphone, hotkey, model, options, probe, done):
            self.pages.addWidget(step)

        self.dots = QLabel()
        self.dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dots.setStyleSheet("font-size: 15px;")
        self.skip_button = QPushButton("Überspringen")
        self.skip_button.clicked.connect(self.skip)
        self.back_button = QPushButton("Zurück")
        self.back_button.clicked.connect(lambda: self._go(self.pages.currentIndex() - 1))
        self.next_button = QPushButton("Weiter")
        self.next_button.setObjectName("primary")
        self.next_button.clicked.connect(self._next)
        footer = QHBoxLayout()
        footer.addWidget(self.skip_button)
        footer.addStretch()
        footer.addWidget(self.back_button)
        footer.addWidget(self.next_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)
        layout.addWidget(self.dots)
        layout.addWidget(self.pages, 1)
        layout.addLayout(footer)
        self._go(0)

    # --- Navigation ---

    @property
    def step(self) -> int:
        return self.pages.currentIndex()

    def _go(self, index: int) -> None:
        self._leave(self.step)
        self.pages.setCurrentIndex(index)
        self.back_button.setEnabled(index > self.WELCOME)
        self.skip_button.setVisible(index < self.DONE)
        self.next_button.setText("Los geht's" if index == self.DONE else "Weiter")
        self.dots.setText(
            "&nbsp;&nbsp;".join(
                f'<span style="color:{ACCENT if i == index else SWITCH_OFF}">●</span>'
                for i in range(self.DONE + 1)
            )
        )
        self._enter(index)

    def _next(self) -> None:
        if self.step == self.DONE:
            self._finish()
        else:
            self._go(self.step + 1)

    def _enter(self, index: int) -> None:
        if index == self.MICROPHONE:
            self._start_mic_test()
        elif index == self.PROBE:
            self._update_probe()
        elif index == self.DONE:
            hotkey = describe_hotkey(self._settings.config.hotkey)
            self.summary.setText(
                f"<p><b>{hotkey} halten</b> – sprechen – loslassen. Der Text erscheint dort, "
                "wo dein Cursor steht.</p>"
                f"<p><b>Zweimal kurz {hotkey} tippen</b> – Freihand-Modus: sprechen, ohne die "
                "Taste zu halten. Einmal tippen beendet ihn.</p>"
                f"<p><b>{hotkey} halten + Rücktaste</b> – das letzte Diktat wieder löschen.</p>"
                "<p>Plaudertaste läuft im Infobereich unten rechts weiter, auch wenn das "
                "Fenster zu ist.</p>"
            )

    def _leave(self, index: int) -> None:
        if index == self.MICROPHONE:
            self._stop_mic_test()
        elif index == self.HOTKEY:
            self.cancel_capture()
        elif index == self.OPTIONS:
            self._apply(
                replace(
                    self._settings.config,
                    sound=self.sound_check.isChecked(),
                    overlay=self.overlay_check.isChecked(),
                    offline_mode=self.offline_check.isChecked(),
                ),
                autostart=self.autostart_check.isChecked(),
            )

    def skip(self) -> None:
        """Mit den aktuellen (Standard-)Werten direkt zum Ende."""
        self._finish()

    def _finish(self) -> None:
        if self._finished:  # X, Esc und "Los geht's" können zusammenfallen
            return
        self._finished = True
        self._leave(self.step)  # u. a. Mikrofon-Test schließen
        self.finished_setup.emit()
        self.accept()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._finish()  # Schließen = Überspringen: bisher gewählte Werte bleiben erhalten
        event.accept()

    def reject(self) -> None:
        self._finish()  # Esc schließt einen Dialog ohne closeEvent – gleich behandeln

    def _apply(self, config: Config, autostart: bool | None = None) -> None:
        self._settings = Settings(
            config, self._settings.autostart if autostart is None else autostart
        )
        self.settings_changed.emit(self._settings)

    # --- Mikrofon-Test ---

    def _on_microphone_changed(self) -> None:
        self._apply(replace(self._settings.config, microphone=self.microphone_box.currentData()))
        if self.step == self.MICROPHONE:
            self._stop_mic_test()
            self._start_mic_test()

    def _start_mic_test(self) -> None:
        self._mic_test = self._recorder_factory(self.microphone_box.currentData())
        try:
            self._mic_test.start()
        except RecorderError as exc:
            self._mic_test = None
            set_hint(self.mic_hint, str(exc))
            return
        set_hint(self.mic_hint, "")
        self._level_timer.start()

    def _stop_mic_test(self) -> None:
        self._level_timer.stop()
        self.level_bar.setValue(0)
        if self._mic_test is not None:
            self._mic_test.stop()  # Mikrofon sofort wieder schließen
            self._mic_test = None

    def _update_level(self) -> None:
        if self._mic_test is not None:
            self.level_bar.setValue(int(level_to_height(self._mic_test.level) * 100))

    # --- Hotkey ---

    def _on_hotkey_clicked(self) -> None:
        if self.hotkey_button.waiting:
            return
        set_hint(self.hotkey_hint, "")
        self.hotkey_button.start_waiting()
        self.capture_requested.emit()

    def set_captured_hotkey(self, hotkey: str) -> None:
        if not self.hotkey_button.waiting:
            return
        problem = hotkey_problem(hotkey)
        self.hotkey_button.show_hotkey(self.hotkey_button.hotkey if problem else hotkey)
        set_hint(self.hotkey_hint, problem or "")
        if not problem:
            self._apply(replace(self._settings.config, hotkey=hotkey))

    def cancel_capture(self) -> None:
        if self.hotkey_button.waiting:
            self.hotkey_button.show_hotkey(self.hotkey_button.hotkey)
            self.capture_cancelled.emit()

    # --- Sprachmodell (vom Controller gemeldet) ---

    def show_model_progress(self, model: str, percent: int) -> None:
        self.model_label.setText(f"Sprachmodell <b>{model}</b> wird heruntergeladen … {percent} %")
        self.model_bar.setRange(0, 100)
        self.model_bar.setValue(percent)
        self._model_percent = percent
        self._update_probe()

    def show_model_ready(self, description: str) -> None:
        self.model_label.setText(f"✓ Bereit: <b>{description}</b>")
        self.model_bar.setRange(0, 100)
        self.model_bar.setValue(100)
        self._model_ready = True
        self._update_probe()

    # --- Probe-Diktat ---

    def _update_probe(self) -> None:
        """Ausgegraut mit Fortschritt, solange das Modell lädt – danach zum Ausprobieren."""
        if not self._model_ready:
            percent = self._model_percent
            progress = "" if percent is None else f" ({percent} %)"
            self.probe_instruction.setText(
                f"Gleich geht's los: Das Sprachmodell wird noch geladen{progress}. Sobald es "
                "bereit ist, kannst du hier ausprobieren – oder schon auf „Weiter“ klicken."
            )
            if percent is not None:
                self.probe_bar.setRange(0, 100)
                self.probe_bar.setValue(percent)
            return
        hotkey = describe_hotkey(self._settings.config.hotkey)
        self.probe_instruction.setText(
            f"<b>Jetzt ausprobieren:</b> Klick ins Feld, halte <b>{hotkey}</b> gedrückt und "
            "sag einen Satz. Beim Loslassen erscheint er hier."
        )
        self.probe_bar.setVisible(False)
        self.probe_field.setEnabled(True)
        if self.step == self.PROBE:
            self.probe_field.setFocus()

    def _on_probe_text(self) -> None:
        if self.probe_field.toPlainText().strip():
            self.probe_result.setText("✓ Klappt! So funktioniert es in jedem Programm.")
