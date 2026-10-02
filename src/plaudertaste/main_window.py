"""Hauptfenster mit Seitenleiste: Start, Verlauf, Statistik, Einstellungen.

Das Schließen-Kreuz versteckt das Fenster nur – Plaudertaste läuft im Infobereich weiter.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import IntEnum

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from plaudertaste import __version__
from plaudertaste.app import Status
from plaudertaste.history import Entry, History
from plaudertaste.settings_page import SettingsPage
from plaudertaste.stats import TYPING_WPM, Stats, Totals
from plaudertaste.tray import STATUS_COLORS
from plaudertaste.ui import card, card_title, format_duration, format_number, muted_label, page_title


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


def _big_number(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setObjectName("bigNumber")
    return label


class StartPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.status_dot = QLabel("●")
        self.status_text = QLabel()
        self.status_text.setObjectName("pageTitle")
        self.status_dot.setObjectName("pageTitle")
        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_text)
        status_row.addStretch()
        self.instructions = QLabel()
        self.instructions.setWordWrap(True)

        self.words_value = _big_number()
        self.dictations_value = _big_number()
        self.saved_value = _big_number()
        tiles = QHBoxLayout()
        tiles.setSpacing(14)
        for title, value in (
            ("Wörter heute", self.words_value),
            ("Diktate heute", self.dictations_value),
            ("Heute gespart (ca.)", self.saved_value),
        ):
            tiles.addWidget(card(muted_label(title), value, spacing=4))

        self.model_label = QLabel()
        self.language_label = QLabel()
        self.microphone_label = QLabel()
        details = QGridLayout()
        details.setHorizontalSpacing(24)
        details.setVerticalSpacing(8)
        for row, (name, value) in enumerate(
            [("Modell", self.model_label), ("Sprache", self.language_label),
             ("Mikrofon", self.microphone_label)]
        ):
            details.addWidget(muted_label(name), row, 0)
            details.addWidget(value, row, 1)
        details.setColumnStretch(1, 1)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(card(status_row, self.instructions))
        layout.addLayout(tiles)
        layout.addWidget(card(card_title("Aktuelle Einstellungen"), details))
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
        self.words_value.setText(format_number(totals.words))
        self.dictations_value.setText(format_number(totals.dictations))
        self.saved_value.setText(format_duration(totals.saved_seconds))


class HistoryPage(QWidget):
    def __init__(self, history: History, copy: Callable[[str], None]) -> None:
        super().__init__()
        self._history = history
        self._copy = copy

        self._list = QVBoxLayout()
        self._list.setSpacing(10)
        self._list.setContentsMargins(0, 0, 6, 0)  # Platz für die Scrollleiste
        self._list.addStretch()
        container = QWidget()
        container.setLayout(self._list)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)

        self.empty_label = muted_label(
            "Noch keine Diktate seit dem Start. Halte deinen Hotkey gedrückt und sprich – "
            "hier erscheint dann jedes Diktat zum erneuten Kopieren."
        )
        self.clear_button = QPushButton("Verlauf leeren")
        self.clear_button.clicked.connect(self._clear)
        footer = QHBoxLayout()
        footer.addWidget(
            muted_label("Nur im Arbeitsspeicher – nach dem Beenden ist der Verlauf weg."), 1
        )
        footer.addWidget(self.clear_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
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
        text = QLabel(entry.text)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        copy_button = QPushButton("Kopieren")
        copy_button.clicked.connect(lambda: self._copy(entry.text))
        header = QHBoxLayout()
        header.addWidget(muted_label(f"{entry.time:%H:%M} · {format_duration(entry.seconds)}"))
        header.addStretch()
        header.addWidget(copy_button)
        return card(header, text, spacing=6)

    def _clear(self) -> None:
        self._history.clear()
        self.refresh()


class StatsPage(QWidget):
    COLUMNS = ("Heute", "Diese Woche", "Insgesamt")

    def __init__(self, stats: Stats) -> None:
        super().__init__()
        self._stats = stats
        # Pro Spalte: große Wortzahl plus drei Detailzeilen
        self._words: list[QLabel] = []
        self._details: list[dict[str, QLabel]] = []
        columns = QHBoxLayout()
        columns.setSpacing(14)
        for title in self.COLUMNS:
            words = _big_number()
            details = {name: QLabel() for name in ("Diktate", "Sprechzeit", "Gespart (ca.)")}
            grid = QGridLayout()
            grid.setVerticalSpacing(6)
            for row, (name, value) in enumerate(details.items()):
                value.setAlignment(Qt.AlignmentFlag.AlignRight)
                grid.addWidget(muted_label(name), row, 0)
                grid.addWidget(value, row, 1)
            columns.addWidget(card(card_title(title), words, muted_label("Wörter"), grid, spacing=6))
            self._words.append(words)
            self._details.append(details)

        self.reset_button = QPushButton("Statistik zurücksetzen")
        self.reset_button.clicked.connect(self._reset)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(self.reset_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(page_title("Statistik"))
        layout.addLayout(columns)
        layout.addWidget(
            muted_label(
                f"Gesparte Zeit ist eine Schätzung: Tippen mit {TYPING_WPM} Wörtern pro Minute "
                "minus Sprechzeit. Gespeichert werden nur diese Zahlen, nie dein Text."
            )
        )
        layout.addStretch()
        layout.addLayout(footer)

    def words(self, column: int) -> str:
        return self._words[column].text()

    def detail(self, column: int, name: str) -> str:
        return self._details[column][name].text()

    def refresh(self) -> None:
        for column, totals in enumerate(
            (self._stats.today(), self._stats.this_week(), self._stats.total())
        ):
            self._words[column].setText(format_number(totals.words))
            details = self._details[column]
            details["Diktate"].setText(format_number(totals.dictations))
            details["Sprechzeit"].setText(format_duration(totals.seconds))
            details["Gespart (ca.)"].setText(format_duration(totals.saved_seconds))

    def _reset(self) -> None:
        answer = QMessageBox.question(
            self, "Statistik zurücksetzen", "Alle Statistik-Werte löschen?"
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._stats.reset()
            self.refresh()


class DownloadBanner(QWidget):
    """Schmaler Hinweis über allen Seiten, solange ein Sprachmodell heruntergeladen wird."""

    cancel_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.cancel_button = QPushButton("Abbrechen")
        self.cancel_button.clicked.connect(self.cancel_requested)
        header = QHBoxLayout()
        header.addWidget(self.text, 1)
        header.addWidget(self.cancel_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(37, 20, 37, 0)  # bündig mit den Karten der Seiten
        layout.addWidget(card(header, self.bar, spacing=8))
        self.setVisible(False)

    def show_progress(self, model: str, done: int, total: int) -> None:
        percent = done * 100 // total if total else 0
        self.text.setText(
            f"Sprachmodell „{model}“ wird heruntergeladen … <b>{percent} %</b> "
            f"({format_number(done // 1_000_000)} von {format_number(total // 1_000_000)} MB). "
            "Das passiert nur einmal."
        )
        self.bar.setValue(percent)
        self.cancel_button.setEnabled(True)
        self.setVisible(True)


class MainWindow(QMainWindow):
    hidden_to_tray = Signal()

    def __init__(
        self, icon: QIcon, settings_page: SettingsPage, history: History, stats: Stats
    ) -> None:
        super().__init__()
        self.setWindowTitle("Plaudertaste")
        self.setWindowIcon(icon)
        self.resize(900, 640)
        self.setMinimumSize(760, 520)

        self.start_page = StartPage()
        self.history_page = HistoryPage(history, QGuiApplication.clipboard().setText)
        self.stats_page = StatsPage(stats)
        self.settings_page = settings_page
        self.download_banner = DownloadBanner()

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("nav")
        self.pages = QStackedWidget()
        for page, widget in zip(
            Page, (self.start_page, self.history_page, self.stats_page, self.settings_page)
        ):
            self.sidebar.addItem(_PAGE_NAMES[page])
            # Verlauf und Einstellungen scrollen selbst (mit fester Fußleiste); Start und
            # Statistik scrollen als Ganzes, statt bei kleinem Fenster gequetscht zu werden.
            scrollable = page in (Page.START, Page.STATS)
            self.pages.addWidget(_padded(widget, scrollable))
        self.sidebar.currentRowChanged.connect(self._on_page_changed)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar(icon))
        content = QVBoxLayout()
        content.setSpacing(0)
        content.addWidget(self.download_banner)
        content.addWidget(self.pages, 1)
        layout.addLayout(content, 1)
        self.setCentralWidget(central)
        self.sidebar.setCurrentRow(Page.START)

    def _build_sidebar(self, icon: QIcon) -> QWidget:
        logo = QLabel()
        logo.setPixmap(icon.pixmap(28, 28))
        name = QLabel("Plaudertaste")
        name.setObjectName("appName")
        brand = QHBoxLayout()
        brand.setContentsMargins(20, 20, 20, 16)
        brand.setSpacing(10)
        brand.addWidget(logo)
        brand.addWidget(name)
        brand.addStretch()

        version = muted_label(f"Version {__version__}")
        version.setContentsMargins(24, 0, 0, 16)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        sidebar.setFixedWidth(200)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(brand)
        layout.addWidget(self.sidebar, 1)
        layout.addWidget(version)
        return sidebar

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


def _padded(widget: QWidget, scrollable: bool) -> QWidget:
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(28, 24, 28, 20)
    layout.addWidget(widget)
    if not scrollable:
        return wrapper
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(wrapper)
    return scroll
