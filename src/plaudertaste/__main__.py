"""Startpunkt: `python -m plaudertaste` bzw. `plaudertaste`."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from plaudertaste import __version__, paths
from plaudertaste.app import App
from plaudertaste.config import ConfigError, load_config
from plaudertaste.hotkey import PushToTalk, parse_hotkey, start_listener
from plaudertaste.logging_setup import setup_logging
from plaudertaste.recorder import Recorder
from plaudertaste.single_instance import acquire_single_instance_lock
from plaudertaste.transcriber import Transcriber

log = logging.getLogger("plaudertaste")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="plaudertaste", description="Push-to-Talk-Diktat, 100 % lokal."
    )
    parser.add_argument(
        "--console", action="store_true", help="Meldungen zusätzlich live in der Konsole zeigen"
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

    lock = acquire_single_instance_lock(paths.lock_file())
    if lock is None:
        log.error("Plaudertaste läuft bereits – zweiter Start abgebrochen.")
        return 1

    config_path = paths.config_file()
    try:
        config = load_config(config_path)
        combo = parse_hotkey(config.hotkey)
    except (ConfigError, ValueError) as exc:
        log.error("Konfiguration ungültig: %s (Datei: %s)", exc, config_path)
        return 1
    log.info("Konfiguration: %s", config_path)

    try:
        transcriber = Transcriber(config.model, config.device, config.language)
    except Exception:
        log.exception("Modell konnte nicht geladen werden. Beim ersten Start wird eine "
                      "Internetverbindung für den Download benötigt.")
        return 1
    log.info("Modell '%s' bereit (%s).", transcriber.choice.name, transcriber.choice.device.upper())

    app = App(transcriber, Recorder())
    app.start()
    listener = start_listener(PushToTalk(combo, app.on_start, app.on_stop, app.on_cancel))
    log.info("Bereit! Halte [%s] gedrückt und sprich. Beenden mit Strg+C.", config.hotkey)

    try:
        while listener.is_alive():
            listener.join(0.5)  # mit Timeout, damit Strg+C unter Windows ankommt
    except KeyboardInterrupt:
        log.info("Beendet.")
    finally:
        listener.stop()
        app.stop()
        lock.unlock()
    return 0


if __name__ == "__main__":
    sys.exit(main())
