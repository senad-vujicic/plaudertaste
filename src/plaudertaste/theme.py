"""Dunkles Design mit violettem Akzent – alle Farben an einer Stelle.

Basis ist Qts Stil "Fusion": Der Windows-Stil ignoriert viele Stylesheet-Angaben.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

BACKGROUND = "#16161a"
SIDEBAR = "#1c1c22"
SURFACE = "#212129"  # Karten, Eingabefelder
SURFACE_HOVER = "#2a2a34"
BORDER = "#2f2f3a"
TEXT = "#ececf1"
MUTED = "#9a9aab"
ACCENT = "#7c5cff"
ACCENT_HOVER = "#8f74ff"
ACCENT_PRESSED = "#6a4ae6"
ACCENT_SOFT = "#2b2545"  # Auswahl-Hintergrund in der Seitenleiste
SUCCESS = "#22c55e"
HINT = "#f0a63a"

STYLESHEET = f"""
QWidget {{
    color: {TEXT};
    font-size: 10pt;
}}
QMainWindow, QDialog, QMessageBox {{ background: {BACKGROUND}; }}

QLabel#muted {{ color: {MUTED}; }}
QLabel#hint {{ color: {HINT}; }}
QLabel#success {{ color: {SUCCESS}; font-weight: 600; }}
QLabel#pageTitle {{ font-size: 20pt; font-weight: 600; }}
QLabel#cardTitle {{ font-size: 11pt; font-weight: 600; }}
QLabel#bigNumber {{ font-size: 22pt; font-weight: 600; }}
QLabel#appName {{ font-size: 13pt; font-weight: 600; }}

QFrame#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#problemCard {{
    background: #2a2216;
    border: 1px solid #6b4e1f;
    border-radius: 12px;
}}
QWidget#sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}

QListWidget#nav {{ background: transparent; border: none; outline: 0; }}
QListWidget#nav::item {{
    padding: 10px 14px;
    margin: 2px 10px;
    border-radius: 8px;
    color: {MUTED};
}}
QListWidget#nav::item:hover {{ background: {SURFACE_HOVER}; color: {TEXT}; }}
QListWidget#nav::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; }}

QPushButton {{
    background: {SURFACE_HOVER};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 16px;
    min-height: 20px;
}}
QPushButton:hover {{ background: #33333f; }}
QPushButton:pressed {{ background: #2a2a34; }}
QPushButton:disabled {{ color: #5c5c6b; background: {SURFACE}; }}
QPushButton#primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primary:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#primary:disabled {{ background: #3a3550; border-color: #3a3550; color: #8d86a8; }}

QComboBox {{
    background: {BACKGROUND};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 10px;
    min-height: 20px;
}}
QComboBox:hover, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_SOFT};
    outline: 0;
}}

QLineEdit {{
    background: {BACKGROUND};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 10px;
    min-height: 20px;
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}

QListWidget#entries, QTableWidget {{
    background: {BACKGROUND};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    outline: 0;
}}
QListWidget#entries::item, QTableWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
QListWidget#entries::item:selected, QTableWidget::item:selected {{
    background: {ACCENT_SOFT};
    color: {TEXT};
}}
QHeaderView::section {{
    background: {SURFACE};
    color: {MUTED};
    border: none;
    padding: 6px 8px;
}}
QTableCornerButton::section {{ background: {SURFACE}; border: none; }}

QProgressBar {{
    background: {BACKGROUND};
    border: 1px solid {BORDER};
    border-radius: 5px;
    max-height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #3a3a46; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

QMenu {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT_SOFT}; }}
QMenu::item:disabled {{ color: {MUTED}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}

QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, BACKGROUND),
        (QPalette.ColorRole.Base, SURFACE),
        (QPalette.ColorRole.AlternateBase, SURFACE_HOVER),
        (QPalette.ColorRole.Text, TEXT),
        (QPalette.ColorRole.WindowText, TEXT),
        (QPalette.ColorRole.ButtonText, TEXT),
        (QPalette.ColorRole.Button, SURFACE_HOVER),
        (QPalette.ColorRole.Highlight, ACCENT),
        (QPalette.ColorRole.HighlightedText, "#ffffff"),
        (QPalette.ColorRole.PlaceholderText, MUTED),
        (QPalette.ColorRole.ToolTipBase, SURFACE),
        (QPalette.ColorRole.ToolTipText, TEXT),
    ):
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#5c5c6b"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#5c5c6b"))
    app.setPalette(palette)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLESHEET)
