"""Baut die Windows-Version nach dist/Plaudertaste/.

Aufruf (im venv, mit `pip install -e .[gpu,build]`):
    python packaging/build.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import PyInstaller.__main__
from PySide6.QtCore import QBuffer, QIODevice, QSize
from PySide6.QtGui import QGuiApplication

from plaudertaste.tray import make_app_icon

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(size: int) -> bytes:
    pixmap = make_app_icon().pixmap(QSize(size, size))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(buffer.data())


def write_ico(path: Path, images: dict[int, bytes]) -> None:
    """Schreibt eine .ico-Datei mit PNG-Bildern (seit Windows Vista unterstützt)."""
    header = struct.pack("<HHH", 0, 1, len(images))  # reserviert, Typ 1 = Icon, Anzahl
    offset = len(header) + 16 * len(images)
    entries, data = b"", b""
    for size, png in images.items():
        # Breite/Höhe 0 bedeutet 256 Pixel; Farbebenen 1, 32 Bit pro Pixel
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
        data += png
    path.write_bytes(header + entries + data)


def main() -> int:
    app = QGuiApplication(sys.argv[:1])  # nötig, damit Qt das Icon zeichnen kann
    BUILD_DIR.mkdir(exist_ok=True)
    write_ico(BUILD_DIR / "plaudertaste.ico", {size: png_bytes(size) for size in ICON_SIZES})
    del app

    PyInstaller.__main__.run(
        [
            str(ROOT / "packaging" / "plaudertaste.spec"),
            "--noconfirm",
            "--clean",
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(BUILD_DIR / "pyinstaller"),
        ]
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
