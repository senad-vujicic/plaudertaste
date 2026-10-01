"""Logging in eine rotierende Datei und optional in die Konsole.

Datenschutz: Diktierter Text wird nie geloggt – nur Abläufe, Zeiten und Fehler.
"""

from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

LOG_FILE_NAME = "plaudertaste.log"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3

_NOISY_LOGGERS = ("httpx", "httpcore", "faster_whisper", "huggingface_hub")


def setup_logging(directory: Path, console: bool) -> Path:
    """Richtet das Logging ein und gibt den Pfad der Logdatei zurück."""
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / LOG_FILE_NAME

    file_handler = RotatingFileHandler(
        log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    )
    handlers: list[logging.Handler] = [file_handler]

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
        handlers.append(console_handler)

    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    _log_uncaught_exceptions()
    return log_file


def _log_uncaught_exceptions() -> None:
    """Abstürze – auch in Hintergrund-Threads – landen in der Logdatei."""
    log = logging.getLogger("plaudertaste")

    def main_hook(
        exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None
    ) -> None:
        log.critical("Unerwarteter Fehler", exc_info=(exc_type, exc, tb))

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_value is not None:
            log.critical(
                "Unerwarteter Fehler im Thread %s",
                args.thread.name if args.thread else "?",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )

    sys.excepthook = main_hook
    threading.excepthook = thread_hook
