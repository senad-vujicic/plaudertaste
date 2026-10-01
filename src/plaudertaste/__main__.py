"""Startpunkt: `python -m plaudertaste` bzw. `plaudertaste`."""

from __future__ import annotations

import logging
import os
import sys

from plaudertaste.app import App
from plaudertaste.config import ConfigError, default_config_path, load_config
from plaudertaste.hotkey import PushToTalk, parse_hotkey, start_listener
from plaudertaste.recorder import Recorder
from plaudertaste.transcriber import Transcriber

log = logging.getLogger("plaudertaste")


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "faster_whisper"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # Ohne Symlinks speichert der Modell-Cache nur Kopien statt Verknüpfungen –
    # bei einer einzigen Modellversion ohne Nachteil, daher Warnung aus.
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def main() -> int:
    _setup_logging()

    config_path = default_config_path()
    try:
        config = load_config(config_path)
        combo = parse_hotkey(config.hotkey)
    except (ConfigError, ValueError) as exc:
        log.error("Konfiguration ungültig: %s\nDatei: %s", exc, config_path)
        return 1
    log.info("Konfiguration: %s", config_path)

    try:
        transcriber = Transcriber(config.model, config.device, config.language)
    except Exception as exc:
        log.error("Modell konnte nicht geladen werden: %s", exc)
        log.error("Beim ersten Start wird eine Internetverbindung für den Download benötigt.")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
