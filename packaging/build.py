"""Baut die Windows-Version: erst den Programmordner dist/Plaudertaste/, dann daraus den
Installer release/Plaudertaste-Setup.exe.

Aufruf (im venv, mit `pip install -e .[gpu,build]`):
    python packaging/build.py
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__
from PySide6.QtCore import QBuffer, QIODevice, QSize
from PySide6.QtGui import QGuiApplication

from plaudertaste import __version__
from plaudertaste.icons import make_app_icon
from plaudertaste.models import MODELS

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


def find_inno_compiler() -> Path | None:
    """ISCC.exe aus dem PATH oder den üblichen Installationsorten von Inno Setup 6."""
    found = shutil.which("ISCC")
    if found:
        return Path(found)
    for variable, sub in (
        ("LOCALAPPDATA", "Programs"),
        ("ProgramFiles(x86)", ""),
        ("ProgramFiles", ""),
    ):
        base = os.environ.get(variable)
        if base:
            candidate = Path(base, sub, "Inno Setup 6", "ISCC.exe")
            if candidate.exists():
                return candidate
    return None


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

    compiler = find_inno_compiler()
    if compiler is None:
        print(
            "Inno Setup 6 nicht gefunden – Installer übersprungen. "
            "Installieren mit: winget install JRSoftware.InnoSetup"
        )
        return 1
    repos = ";".join(model.repo_id for model in MODELS)
    subprocess.run(
        [
            str(compiler),
            f"/DAppVersion={__version__}",
            f"/DModelRepos={repos}",
            str(ROOT / "packaging" / "plaudertaste.iss"),
        ],
        check=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
