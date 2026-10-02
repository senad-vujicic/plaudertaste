"""Startpunkt: `python -m plaudertaste` bzw. `plaudertaste`."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from plaudertaste import __version__, paths
from plaudertaste.logging_setup import setup_logging

log = logging.getLogger("plaudertaste")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="plaudertaste", description="Push-to-Talk-Diktat, 100 % lokal."
    )
    parser.add_argument(
        "--console", action="store_true", help="Meldungen zusätzlich live in der Konsole zeigen"
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="still im Infobereich starten, ohne Fenster (für den Autostart)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    log_file = setup_logging(paths.log_dir(), console=args.console)
    # Ohne Symlinks speichert der Modell-Cache nur Kopien statt Verknüpfungen –
    # bei einer einzigen Modellversion ohne Nachteil, daher Warnung aus.
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    log.info("Plaudertaste %s startet. Logdatei: %s", __version__, log_file)

    # Qt und Whisper erst hier laden: so bleiben --help/--version schnell, und
    # Importfehler landen bereits in der Logdatei.
    from plaudertaste import gui

    return gui.run(log_file, show_window=not args.background)


if __name__ == "__main__":
    sys.exit(main())
