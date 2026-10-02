"""Dunkles Schiefer-Design mit Mint, Pink und Lavendel – alle Farben an einer Stelle.

Basis ist Qts Stil "Fusion": Der Windows-Stil ignoriert viele Stylesheet-Angaben.
Schrift ist Poppins (SIL Open Font License), mitgeliefert in assets/fonts.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

ASSET_DIR = Path(__file__).parent / "assets"
FONT_DIR = ASSET_DIR / "fonts"
FONT_FAMILY = "Poppins"
FALLBACK_FONT = "Segoe UI"  # falls die mitgelieferte Schrift nicht geladen werden kann

BACKGROUND = "#283037"  # Schiefergrau-Blau
SIDEBAR = "#22313e"
SURFACE = "#2f3840"  # Karten
SURFACE_HOVER = "#38434c"  # Knöpfe
INPUT = "#252d33"  # Eingabefelder und Listen – etwas tiefer als die Karte
BORDER = "#3a4550"
TEXT = "#eef1f4"
MUTED = "#8d99a6"
DISABLED = "#66727c"

HIGHLIGHT = "#f4f6f8"  # die eine helle Karte und die gewählte Seite in der Seitenleiste
INK = "#1d252b"  # dunkle Schrift auf Hell und auf Mint
INK_MUTED = "#5b6670"

ACCENT = "#6ee7c3"  # Mint
ACCENT_HOVER = "#8ff0d3"
ACCENT_PRESSED = "#4fd1ab"
ACCENT_DEEP = "#3fae8f"  # Seitenwand der Tasten im Logo
ACCENT_SOFT = "#30504a"  # Auswahl in Listen
PINK = "#ef476f"
LAVENDER = "#c6c1f2"
HINT = "#f5b54a"
SWITCH_OFF = "#46525c"

# Statusfarben – Tray-Symbol, Overlay und Startseite nutzen dieselben
STATUS_LOADING = MUTED
STATUS_READY = ACCENT
STATUS_RECORDING = PINK
STATUS_PROCESSING = LAVENDER

STYLESHEET = f"""
QWidget {{
    color: {TEXT};
    font-family: "{FONT_FAMILY}", "{FALLBACK_FONT}";
    font-size: 9.5pt;
}}
QMainWindow, QDialog, QMessageBox {{ background: {BACKGROUND}; }}

QLabel#muted {{ color: {MUTED}; }}
QLabel#hint {{ color: {HINT}; }}
QLabel#success {{ color: {ACCENT}; font-weight: 600; }}
QLabel#pageTitle {{ font-size: 18pt; font-weight: 600; }}
QLabel#cardTitle {{ font-size: 10.5pt; font-weight: 500; }}
QLabel#bigNumber {{ font-size: 22pt; font-weight: 600; }}
QLabel#appName {{ font-size: 12pt; font-weight: 600; }}

QFrame#card {{
    background: {SURFACE};
    border: none;
    border-radius: 16px;
}}
QFrame#heroCard {{
    background: {HIGHLIGHT};
    border: none;
    border-radius: 16px;
}}
QFrame#heroCard QLabel {{ color: {INK}; }}
QFrame#heroCard QLabel#muted {{ color: {INK_MUTED}; }}
QFrame#problemCard {{
    background: #3a3427;
    border: 1px solid #6b5628;
    border-radius: 16px;
}}
QWidget#sidebar {{ background: {SIDEBAR}; }}

QListWidget#nav {{ background: transparent; border: none; outline: 0; }}
QListWidget#nav::item {{
    padding: 9px 12px;
    margin: 3px 14px;
    border-radius: 10px;
    color: {MUTED};
}}
QListWidget#nav::item:hover {{ background: {SURFACE}; color: {TEXT}; }}
QListWidget#nav::item:selected {{ background: {HIGHLIGHT}; color: {INK}; }}

QPushButton {{
    background: {SURFACE_HOVER};
    border: none;
    border-radius: 10px;
    padding: 8px 18px;
    min-height: 20px;
}}
QPushButton:hover {{ background: #424e58; }}
QPushButton:pressed {{ background: #333d46; }}
QPushButton:disabled {{ color: {DISABLED}; background: {SURFACE}; }}
QPushButton#primary {{
    background: {ACCENT};
    color: {INK};
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primary:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#primary:disabled {{ background: #3b524d; color: #7d978f; }}

QComboBox {{
    background: {INPUT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 7px 10px;
    min-height: 20px;
}}
QComboBox:hover, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; background: transparent; width: 28px; }}
QComboBox::down-arrow {{
    image: url("{(ASSET_DIR / "chevron-down.svg").as_posix()}");
    width: 12px;
    height: 12px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_SOFT};
    outline: 0;
}}

QLineEdit, QPlainTextEdit {{
    background: {INPUT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 7px 10px;
    min-height: 20px;
}}
QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}

QListWidget#entries, QTableWidget {{
    background: {INPUT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px;
    outline: 0;
}}
QListWidget#entries::item, QTableWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
QListWidget#entries::item:selected, QTableWidget::item:selected {{
    background: {ACCENT_SOFT};
    color: {TEXT};
}}
QHeaderView::section {{
    background: {INPUT};
    color: {MUTED};
    border: none;
    padding: 6px 8px;
}}
QTableCornerButton::section {{ background: {INPUT}; border: none; }}

QProgressBar {{
    background: {INPUT};
    border: none;
    border-radius: 5px;
    max-height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {SWITCH_OFF}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

QMenu {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT_SOFT}; }}
QMenu::item:disabled {{ color: {MUTED}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}

QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; }}
"""


def load_fonts() -> bool:
    """Registriert die mitgelieferte Schrift bei Qt. False, wenn keine Datei ladbar war."""
    loaded = [QFontDatabase.addApplicationFont(str(path)) for path in FONT_DIR.glob("*.ttf")]
    return any(font_id != -1 for font_id in loaded)


def ui_font(point_size: float) -> QFont:
    """Poppins in der gewünschten Größe – mit Windows-Schrift als Rückfallebene."""
    font = QFont([FONT_FAMILY, FALLBACK_FONT])
    font.setPointSizeF(point_size)
    return font


def apply_theme(app: QApplication) -> None:
    load_fonts()
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, BACKGROUND),
        (QPalette.ColorRole.Base, INPUT),
        (QPalette.ColorRole.AlternateBase, SURFACE),
        (QPalette.ColorRole.Text, TEXT),
        (QPalette.ColorRole.WindowText, TEXT),
        (QPalette.ColorRole.ButtonText, TEXT),
        (QPalette.ColorRole.Button, SURFACE_HOVER),
        (QPalette.ColorRole.Highlight, ACCENT),
        (QPalette.ColorRole.HighlightedText, INK),
        (QPalette.ColorRole.PlaceholderText, MUTED),
        (QPalette.ColorRole.ToolTipBase, SURFACE),
        (QPalette.ColorRole.ToolTipText, TEXT),
    ):
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(DISABLED))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(DISABLED))
    app.setPalette(palette)
    app.setFont(ui_font(9.5))
    app.setStyleSheet(STYLESHEET)
