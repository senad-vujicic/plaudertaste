"""Wörterbuch-Seite: Begriffe und Ersetzungen – jede Änderung wird sofort gespeichert."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from plaudertaste.dictionary import Dictionary
from plaudertaste.ui import (
    SavedIndicator,
    card,
    card_title,
    hint_label,
    muted_label,
    page_title,
    scrolling_column,
    set_hint,
)

TOO_MANY_TERMS_HINT = (
    "Sehr viele Begriffe: Whisper kann nur einen begrenzten Hinweis aufnehmen, die letzten "
    "Begriffe werden womöglich nicht mehr berücksichtigt."
)


class DictionaryPage(QWidget):
    changed = Signal(object)  # Dictionary – nach jeder Änderung

    def __init__(self) -> None:
        super().__init__()
        self._dictionary = Dictionary()

        # --- Begriffe ---
        self.term_input = QLineEdit()
        self.term_input.setPlaceholderText("Neuer Begriff, z. B. Plaudertaste")
        self.term_input.returnPressed.connect(self._add_term)
        add_term = QPushButton("Hinzufügen")
        add_term.clicked.connect(self._add_term)
        term_row = QHBoxLayout()
        term_row.addWidget(self.term_input, 1)
        term_row.addWidget(add_term)

        self.term_list = QListWidget()
        self.term_list.setObjectName("entries")
        self.term_list.setMinimumHeight(140)
        self.term_list.itemSelectionChanged.connect(self._update_buttons)
        self.remove_term_button = QPushButton("Entfernen")
        self.remove_term_button.clicked.connect(self._remove_term)
        self.terms_hint = hint_label()

        terms_card = card(
            card_title("Begriffe"),
            muted_label(
                "Namen und Fachwörter, die richtig erkannt und geschrieben werden sollen – "
                "zum Beispiel Nachnamen, Firmen oder Fachbegriffe."
            ),
            term_row,
            self.term_list,
            _right(self.remove_term_button),
            self.terms_hint,
        )

        # --- Ersetzungen ---
        self.spoken_input = QLineEdit()
        self.spoken_input.setPlaceholderText("Gesagt, z. B. mfg")
        # Mehrzeilig, damit auch Textbausteine wie eine komplette Signatur hineinpassen.
        self.written_input = QPlainTextEdit()
        self.written_input.setPlaceholderText(
            "Geschrieben, z. B. Mit freundlichen Grüßen – darf mehrzeilig sein"
        )
        self.written_input.setTabChangesFocus(True)
        self.written_input.setFixedHeight(64)
        self.spoken_input.returnPressed.connect(self._add_replacement)
        add_replacement = QPushButton("Hinzufügen")
        add_replacement.clicked.connect(self._add_replacement)
        replacement_row = QHBoxLayout()
        replacement_row.addWidget(self.spoken_input, 2)
        replacement_row.addWidget(QLabel("→"))
        replacement_row.addWidget(self.written_input, 3)
        replacement_row.addWidget(add_replacement)

        self.replacement_table = QTableWidget(0, 2)
        self.replacement_table.setHorizontalHeaderLabels(["Gesagt", "Geschrieben"])
        self.replacement_table.verticalHeader().setVisible(False)
        self.replacement_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.replacement_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.replacement_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.replacement_table.setShowGrid(False)
        self.replacement_table.setMinimumHeight(160)
        self.replacement_table.itemSelectionChanged.connect(self._update_buttons)
        self.remove_replacement_button = QPushButton("Entfernen")
        self.remove_replacement_button.clicked.connect(self._remove_replacement)

        replacements_card = card(
            card_title("Ersetzungen"),
            muted_label(
                "Wird nach der Erkennung automatisch ausgetauscht – nur ganze Wörter, "
                "Groß-/Kleinschreibung egal. Gleiches „Gesagt“ überschreibt den alten Eintrag. "
                "Auch für Textbausteine: z. B. „meine Signatur“ → deine komplette Signatur."
            ),
            replacement_row,
            self.replacement_table,
            _right(self.remove_replacement_button),
        )

        self.saved_label = SavedIndicator()
        header = QHBoxLayout()
        header.addWidget(page_title("Wörterbuch"))
        header.addStretch()
        header.addWidget(self.saved_label)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addLayout(header)
        layout.addWidget(scrolling_column(terms_card, replacements_card), 1)
        self._update_buttons()

    def set_dictionary(self, dictionary: Dictionary) -> None:
        """Zeigt den gespeicherten Stand an (ohne "geändert" zu melden)."""
        self._dictionary = dictionary
        self.term_list.clear()
        self.term_list.addItems(list(dictionary.terms))
        self.replacement_table.setRowCount(len(dictionary.replacements))
        for row, replacement in enumerate(dictionary.replacements):
            self.replacement_table.setItem(row, 0, QTableWidgetItem(replacement.spoken))
            # Zeilenumbrüche in der Tabelle sichtbar machen, ohne die Zeile aufzublähen
            shown = replacement.written.replace("\n", " ⏎ ")
            self.replacement_table.setItem(row, 1, QTableWidgetItem(shown))
        set_hint(self.terms_hint, TOO_MANY_TERMS_HINT if dictionary.hint_too_long() else "")
        self._update_buttons()

    def show_saved(self) -> None:
        self.saved_label.flash()

    def _apply(self, dictionary: Dictionary) -> None:
        if dictionary == self._dictionary:
            return
        self.set_dictionary(dictionary)
        self.changed.emit(dictionary)

    def _add_term(self) -> None:
        self._apply(self._dictionary.with_term(self.term_input.text()))
        self.term_input.clear()

    def _remove_term(self) -> None:
        dictionary = self._dictionary
        for item in self.term_list.selectedItems():
            dictionary = dictionary.without_term(item.text())
        self._apply(dictionary)

    def _add_replacement(self) -> None:
        spoken, written = self.spoken_input.text(), self.written_input.toPlainText()
        if not spoken.strip() or not written.strip():
            # Enter im ersten Feld: einfach ins zweite springen
            (self.written_input if spoken.strip() else self.spoken_input).setFocus()
            return
        self._apply(self._dictionary.with_replacement(spoken, written))
        self.spoken_input.clear()
        self.written_input.clear()
        self.spoken_input.setFocus()

    def _remove_replacement(self) -> None:
        dictionary = self._dictionary
        rows = {index.row() for index in self.replacement_table.selectedIndexes()}
        for row in rows:
            dictionary = dictionary.without_replacement(self.replacement_table.item(row, 0).text())
        self._apply(dictionary)

    def _update_buttons(self) -> None:
        self.remove_term_button.setEnabled(bool(self.term_list.selectedItems()))
        self.remove_replacement_button.setEnabled(bool(self.replacement_table.selectedIndexes()))


def _right(widget: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.addStretch()
    row.addWidget(widget)
    return row
