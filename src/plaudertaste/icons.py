"""Alle Symbole, im Code gezeichnet: das Tasten-Logo, die farbigen Tray-Symbole und die
Linien-Symbole der Seitenleiste. (Einzige Bilddatei: der Auswahlfeld-Pfeil, weil Qt-Stylesheets
dafür eine Datei brauchen – siehe theme.py.)

Das Logo ist eine Taste mit Schallwellen – Taste + Stimme = Plaudertaste. Groß wird sie
schräg von oben gezeigt, in kleinen Größen (≤ 24 px) von vorn, weil sie sonst verschwimmt.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap, QPolygonF, QTransform
from PySide6.QtSvg import QSvgRenderer

from plaudertaste import theme
from plaudertaste.app import Status

STATUS_COLORS: dict[Status, str] = {
    Status.LOADING: theme.STATUS_LOADING,
    Status.READY: theme.STATUS_READY,
    Status.RECORDING: theme.STATUS_RECORDING,
    Status.PROCESSING: theme.STATUS_PROCESSING,
}
TRAY_SIZES = (16, 24, 32, 48, 64)
APP_ICON_SIZES = (*TRAY_SIZES, 128, 256)
FRONT_VIEW_MAX = 24  # bis zu dieser Größe die Frontansicht
WAVE_HEIGHTS = (0.35, 0.7, 1.0, 0.6, 0.3)  # Schallwellen von links nach rechts


def _blank(size: int) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    return pixmap, painter


def paint_waves(painter: QPainter, area: QRectF, color: str) -> None:
    """Fünf abgerundete Balken, mittig in `area`."""
    count = len(WAVE_HEIGHTS)
    bar = area.width() / (count * 1.7)
    gap = (area.width() - count * bar) / (count - 1)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    for i, height in enumerate(WAVE_HEIGHTS):
        h = area.height() * height
        x = area.left() + i * (bar + gap)
        painter.drawRoundedRect(QRectF(x, area.center().y() - h / 2, bar, h), bar / 2, bar / 2)


def paint_keycap(painter: QPainter, rect: QRectF, top: QColor, side: QColor) -> QRectF:
    """Taste von vorn: Sockel plus nach oben versetzte Oberseite. Gibt die Oberseite zurück."""
    radius = min(rect.width(), rect.height()) * 0.2
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(side)
    painter.drawRoundedRect(rect.adjusted(0, rect.height() * 0.04, 0, 0), radius, radius)
    inset = rect.width() * 0.1 if rect.width() < rect.height() * 1.6 else rect.height() * 0.12
    top_face = QRectF(
        rect.left() + inset,
        rect.top(),
        rect.width() - 2 * inset,
        rect.height() * 0.76,
    )
    painter.setBrush(top)
    painter.drawRoundedRect(top_face, radius * 0.75, radius * 0.75)
    return top_face


def front_keycap(size: int, color: str) -> QPixmap:
    """Frontansicht mit Schallwellen – fürs Tray (Farbe = Status) und kleine App-Symbole."""
    pixmap, painter = _blank(size)
    s = size / 64
    top = QColor(color)
    top_face = paint_keycap(painter, QRectF(5 * s, 6 * s, 54 * s, 54 * s), top, top.darker(140))
    paint_waves(painter, top_face.adjusted(9 * s, 9 * s, -9 * s, -9 * s), theme.INK)
    painter.end()
    return pixmap


def _convex_hull(points: list[QPointF]) -> QPolygonF:
    """Umriss um alle Punkte (Andrew-Monotone-Chain) – ergibt die Seitenwand der Taste."""
    pts = sorted({(round(p.x(), 3), round(p.y(), 3)) for p in points})

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    upper: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return QPolygonF([QPointF(x, y) for x, y in lower[:-1] + upper[:-1]])


def iso_keycap(size: int) -> QPixmap:
    """Das Logo: Taste schräg von oben (isometrisch) mit Schallwellen."""
    pixmap, painter = _blank(size)
    s = size / 64
    iso = QTransform().translate(32 * s, 0).scale(1, 0.58).rotate(45)

    def face(half: float, dy: float, radius: float) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(QRectF(-half, -half, 2 * half, 2 * half), radius, radius)
        return iso.map(path).translated(0, dy)

    top = face(17 * s, 20 * s, 6 * s)
    base = face(21 * s, 34 * s, 7 * s)
    side = _convex_hull(list(top.toFillPolygon()) + list(base.toFillPolygon()))
    painter.setBrush(QColor(theme.ACCENT_DEEP))
    painter.drawPolygon(side)
    painter.setBrush(QColor(theme.ACCENT))
    painter.drawPath(top)
    # Wellen aufrecht, leicht gestaucht – wie von schräg oben gesehen
    paint_waves(painter, QRectF(21 * s, 13 * s, 22 * s, 14 * s), theme.INK)
    painter.end()
    return pixmap


def make_app_icon() -> QIcon:
    """Programm-Symbol für Fenster, Taskleiste und Installer."""
    icon = QIcon()
    for size in APP_ICON_SIZES:
        small = size <= FRONT_VIEW_MAX
        icon.addPixmap(front_keycap(size, theme.ACCENT) if small else iso_keycap(size))
    return icon


def make_status_icon(status: Status) -> QIcon:
    """Tray-Symbol: die Taste in der Farbe des Status."""
    icon = QIcon()
    for size in TRAY_SIZES:
        icon.addPixmap(front_keycap(size, STATUS_COLORS[status]))
    return icon


# --- Seitenleiste: Linien-Symbole (24 × 24), "COLOR" wird durch die Farbe ersetzt ---

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="COLOR" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{}</svg>'
)
NAV_ICONS = {
    "start": '<path d="M3.5 10.5 12 3.5l8.5 7V20a1 1 0 0 1-1 1H15v-6H9v6H4.5a1 1 0 0 1-1-1z"/>',
    "history": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "stats": '<path d="M3 20.5h18"/><path d="M6.5 17V11M12 17V5.5M17.5 17v-8"/>',
    "dictionary": (
        '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z"/>'
        '<path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19M9 8h6"/>'
    ),
    "settings": (
        '<path d="M6 3.5v17M12 3.5v17M18 3.5v17"/>'
        '<circle cx="6" cy="14.5" r="2.3" fill="COLOR"/>'
        '<circle cx="12" cy="8" r="2.3" fill="COLOR"/>'
        '<circle cx="18" cy="16" r="2.3" fill="COLOR"/>'
    ),
}


def _render_svg(svg: str, size: int, scale: int) -> QPixmap:
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(painter, QRectF(pixmap.rect()))
    painter.end()
    pixmap.setDevicePixelRatio(scale)  # scharf auch bei 150/200 % Bildschirm-Skalierung
    return pixmap


def nav_icon(name: str, size: int = 18) -> QIcon:
    """Gedämpft im Normalzustand, dunkel auf der hellen Auswahl-Pille."""
    icon = QIcon()
    for mode, color in ((QIcon.Mode.Normal, theme.MUTED), (QIcon.Mode.Selected, theme.INK)):
        svg = _SVG.format(NAV_ICONS[name]).replace("COLOR", color)
        for scale in (1, 2):
            icon.addPixmap(_render_svg(svg, size, scale), mode)
    return icon
