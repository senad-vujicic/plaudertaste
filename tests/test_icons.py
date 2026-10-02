import pytest
from PySide6.QtGui import QColor, QIcon

from plaudertaste import theme
from plaudertaste.app import Status
from plaudertaste.icons import (
    APP_ICON_SIZES,
    NAV_ICONS,
    STATUS_COLORS,
    TRAY_SIZES,
    front_keycap,
    iso_keycap,
    make_app_icon,
    make_status_icon,
    nav_icon,
)

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.parametrize("status", list(Status))
def test_status_icon_exists_in_all_tray_sizes(status: Status) -> None:
    icon = make_status_icon(status)

    assert sorted(size.width() for size in icon.availableSizes()) == list(TRAY_SIZES)


@pytest.mark.parametrize("status", list(Status))
def test_keycap_top_shows_status_color(status: Status) -> None:
    below_waves = (32, 43)  # auf der Oberseite der Taste, unterhalb der Schallwellen

    color = front_keycap(64, STATUS_COLORS[status]).toImage().pixelColor(*below_waves)

    assert color.name() == QColor(STATUS_COLORS[status]).name()


def test_status_colors_are_distinct() -> None:
    assert len(set(STATUS_COLORS.values())) == len(Status)


def test_app_icon_uses_front_view_only_when_small() -> None:
    icon = make_app_icon()

    assert sorted(size.width() for size in icon.availableSizes()) == list(APP_ICON_SIZES)
    small = icon.pixmap(16).toImage()
    large = icon.pixmap(256).toImage()
    assert small == front_keycap(16, theme.ACCENT).toImage()
    assert large == iso_keycap(256).toImage()


@pytest.mark.parametrize("name", list(NAV_ICONS))
def test_nav_icon_is_drawn_dark_when_selected(name: str) -> None:
    icon = nav_icon(name)

    normal = icon.pixmap(18, QIcon.Mode.Normal).toImage()
    selected = icon.pixmap(18, QIcon.Mode.Selected).toImage()

    assert not normal.isNull()
    assert normal != selected  # andere Farbe auf der hellen Auswahl-Pille
