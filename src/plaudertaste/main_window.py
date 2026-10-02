"""Hauptfenster mit Seitenleiste: Start, Verlauf, Statistik, Einstellungen.

Das Schließen-Kreuz versteckt das Fenster nur – Plaudertaste läuft im Infobereich weiter.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import IntEnum

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from plaudertaste.app import Status
from plaudertaste.history import Entry, History
from plaudertaste.settings_page import SettingsPage
from plaudertaste.stats import TYPING_WPM, Stats, Totals
from plaudertaste.tray import STATUS_COLORS
from plaudertaste.ui import count_text, format_duration, muted_label, page_title


class Page(IntEnum):
    START = 0
    HISTORY = 1
    STATS = 2
    SETTINGS = 3


_PAGE_NAMES = {
    Page.START: "Start",
    Page.HISTORY: "Verlauf",
    Page.STATS: "Statistik",
    Page.SETTINGS: "Einstellungen",
}


class StartPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.status_dot = QLabel("●")
        self.status_text = QLabel()
        status_font = self.status_text.font()
        status_font.setPointSize(20)
        status_font.setBold(True)
        self.status_text.setFont(status_font)
        self.status_dot.setFont(status_font)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_text)
        status_row.addStretch()

        self.instructions = QLabel()
        self.instructions.setWordWrap(True)
        self.model_label = QLabel()
        self.language_label = QLabel()
        self.microphone_label = QLabel()
        self.today_label = QLabel()

        details = QGridLayout()
        for row, (name, value) in enumerate(
            [
                ("Modell", self.model_label),
                ("Sprache", self.language_label),
                ("Mikrofon", self.microphone_label),
                ("Heute", self.today_label),
            ]
        ):
            details.addWidget(muted_label(name), row, 0)
            details.addWidget(value, row, 1)
        details.setColumnStretch(1, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(status_row)
        layout.addSpacing(4)
        layout.addWidget(self.instructions)
        layout.addSpacing(16)
        layout.addLayout(details)
        layout.addStretch()
        layout.addWidget(
            muted_label("100 % lokal: Deine Sprache und dein Text verlassen nie diesen Rechner.")
        )

    def set_status(self, status: Status) -> None:
        self.status_dot.setStyleSheet(f"color: {STATUS_COLORS[status]};")
        self.status_text.setText(status.value)

    def set_info(self, hotkey: str, model: str, language: str, microphone: str) -> None:
        self.instructions.setText(
            f"Halte <b>{hotkey}</b> gedrückt und sprich. Beim Loslassen erscheint der Text "
            "dort, wo dein Cursor steht – in jedem Programm."
        )
        self.model_label.setText(model)
        self.language_label.setText(language)
        self.microphone_label.setText(microphone)

    def set_today(self, totals: Totals) -> None:
        self.today_label.setText(
            f"{count_text(totals.words, 'Wort', 'Wörter')} in "
            f"{count_text(totals.dictations, 'Diktat', 'Diktaten')} · "
            f"ca. {format_duration(totals.saved_seconds)} gespart"
        )


class HistoryPage(QWidget):
    def __init__(self, history: History, copy: Callable[[str], None]) -> None:
        super().__init__()
        self._history = history
        self._copy = copy

        self._list = QVBoxLayout()
        self._list.addStretch()
        container = QWidget()
        container.setLayout(self._list)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(container)

        self.empty_label = muted_label("Noch keine Diktate seit dem Start.")
        self.clear_button = QPushButton("Verlauf leeren")
        self.clear_button.clicked.connect(self._clear)
        footer = QHBoxLayout()
        footer.addWidget(
            muted_label("Nur im Arbeitsspeicher – nach dem Beenden ist der Verlauf weg."), 1
        )
        footer.addWidget(self.clear_button)

        layout = QVBoxLayout(self)
        layout.addWidget(page_title("Verlauf"))
        layout.addWidget(self.empty_label)
        layout.addWidget(scroll, 1)
        layout.addLayout(footer)

    def refresh(self) -> None:
        while self._list.count() > 1:  # alles außer dem Stretch am Ende
            item = self._list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        entries = self._history.entries()
        for index, entry in enumerate(entries):
            self._list.insertWidget(index, self._entry_widget(entry))
        self.empty_label.setVisible(not entries)
        self.clear_button.setEnabled(bool(entries))

    def _entry_widget(self, entry: Entry) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        text = QLabel(entry.text)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        copy_button = QPushButton("Kopieren")
        copy_button.clicked.connect(lambda: self._copy(entry.text))
        header = QHBoxLayout()
        header.addWidget(muted_label(f"{entry.time:%H:%M} · {format_duration(entry.seconds)}"))
        header.addStretch()
        header.addWidget(copy_button)
        layout = QVBoxLayout(frame)
        layout.addLayout(header)
        layout.addWidget(text)
        return frame

    def _clear(self) -> None:
        self._history.clear()
        self.refresh()


class StatsPage(QWidget):
    _ROWS = ("Wörter", "Diktate", "Sprechzeit", "Gespart (ca.)")
    _COLUMNS = ("Heute", "Diese Woche", "Insgesamt")

    def __init__(self, stats: Stats) -> None:
        super().__init__()
        self._stats = stats
        grid = QGridLayout()
        self._cells: dict[tuple[int, int], QLabel] = {}
        for column, name in enumerate(self._COLUMNS, start=1):
            header = QLabel(f"<b>{name}</b>")
            grid.addWidget(header, 0, column, alignment=Qt.AlignmentFlag.AlignRight)
        for row, name in enumerate(self._ROWS, start=1):
            grid.addWidget(muted_label(name), row, 0)
            for column in range(1, len(self._COLUMNS) + 1):
                cell = QLabel()
                cell.setAlignment(Qt.AlignmentFlag.AlignRight)
                grid.addWidget(cell, row, column)
                self._cells[(row, column)] = cell
        grid.setHorizontalSpacing(32)

        self.reset_button = QPushButton("Statistik zurücksetzen")
        self.reset_button.clicked.connect(self._reset)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(self.reset_button)

        layout = QVBoxLayout(self)
        layout.addWidget(page_title("Statistik"))
        layout.addLayout(grid)
        layout.addSpacing(16)
        layout.addWidget(
            muted_label(
                f"Gesparte Zeit ist eine Schätzung: Tippen mit {TYPING_WPM} Wörtern pro Minute "
                "minus Sprechzeit. Gespeichert werden nur diese Zahlen, nie dein Text."
            )
        )
        layout.addStretch()
        layout.addLayout(footer)

    def cell(self, row: int, column: int) -> QLabel:
        return self._cells[(row, column)]

    def refresh(self) -> None:
        for column, totals in enumerate(
            (self._stats.today(), self._stats.this_week(), self._stats.total()), start=1
        ):
            values = (
                f"{totals.words:,}".replace(",", "."),  # Tausenderpunkt
                str(totals.dictations),
                format_duration(totals.seconds),
                format_duration(totals.saved_seconds),
            )
            for row, value in enumerate(values, start=1):
                self.cell(row, column).setText(value)

    def _reset(self) -> None:
        answer = QMessageBox.question(
            self, "Statistik zurücksetzen", "Alle Statistik-Werte löschen?"
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._stats.reset()
            self.refresh()


class MainWindow(QMainWindow):
    hidden_to_tray = Signal()

    def __init__(
        self, icon: QIcon, settings_page: SettingsPage, history: History, stats: Stats
    ) -> None:
        super().__init__()
        self.setWindowTitle("Plaudertaste")
        self.setWindowIcon(icon)
        self.resize(820, 520)

        self.start_page = StartPage()
        self.history_page = HistoryPage(history, QGuiApplication.clipboard().setText)
        self.stats_page = StatsPage(stats)
        self.settings_page = settings_page

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(170)
        self.sidebar.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar.setStyleSheet(
            "QListWidget { font-size: 11pt; padding-top: 8px; }"
            "QListWidget::item { padding: 10px 14px; border-radius: 6px; }"
        )
        self.pages = QStackedWidget()
        for page, widget in zip(
            Page, (self.start_page, self.history_page, self.stats_page, self.settings_page)
        ):
            self.sidebar.addItem(_PAGE_NAMES[page])
            self.pages.addWidget(_padded(widget))
        self.sidebar.currentRowChanged.connect(self._on_page_changed)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(central)
        self.sidebar.setCurrentRow(Page.START)

    def show_page(self, page: Page) -> None:
        self.sidebar.setCurrentRow(page)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def current_page(self) -> Page:
        return Page(self.sidebar.currentRow())

    def refresh(self) -> None:
        """Verlauf und Statistik neu anzeigen (z. B. nach einem Diktat)."""
        self.history_page.refresh()
        self.stats_page.refresh()

    def _on_page_changed(self, row: int) -> None:
        if row != Page.SETTINGS:
            self.settings_page.cancel_capture()
        self.pages.setCurrentIndex(row)

    def closeEvent(self, event: QCloseEvent) -> None:
        # Nur verstecken: Plaudertaste soll im Infobereich weiter diktieren können.
        event.ignore()
        self.settings_page.cancel_capture()
        self.hide()
        self.hidden_to_tray.emit()


def _padded(widget: QWidget) -> QWidget:
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.addWidget(widget)
    return wrapper
