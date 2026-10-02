import pytest
from PySide6.QtGui import QFontDatabase, QFontInfo

from plaudertaste import theme


@pytest.mark.usefixtures("qapp")
def test_bundled_font_is_loaded_and_used() -> None:
    assert theme.load_fonts()
    assert theme.FONT_FAMILY in QFontDatabase.families()
    assert QFontInfo(theme.ui_font(10)).family() == theme.FONT_FAMILY


def test_bundled_assets_exist() -> None:
    assert (theme.FONT_DIR / "OFL.txt").exists()  # Lizenz muss die Schrift begleiten
    assert (theme.ASSET_DIR / "chevron-down.svg").exists()
