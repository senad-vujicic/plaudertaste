"""Update-Hinweis: fragt GitHub einmal, ob es eine neuere Version gibt.

Gesendet wird nur diese eine Anfrage an die GitHub-API – kein Text, keine Sprache.
Im Offline-Modus und bei abgeschalteter Einstellung passiert gar nichts.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)

TIMEOUT_S = 5


@dataclass(frozen=True)
class Update:
    version: str
    url: str  # Seite des Releases zum Herunterladen


def parse_version(text: str) -> tuple[int, ...] | None:
    """"v1.10.0" -> (1, 10, 0). Als Zahlen, damit 0.10.0 neuer ist als 0.9.0."""
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", text.strip())
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def _fetch_latest_release(repo: str) -> dict[str, object]:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Plaudertaste"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return json.load(response)


def check_for_update(
    current: str,
    repo: str,
    fetch: Callable[[str], dict[str, object]] = _fetch_latest_release,
) -> Update | None:
    """Neuere Version oder None. Netzwerkfehler sind kein Fehler fürs Programm."""
    try:
        release = fetch(repo)
    except Exception as exc:  # offline, GitHub nicht erreichbar, noch kein Release …
        log.info("Update-Prüfung nicht möglich: %s", exc)
        return None
    tag = str(release.get("tag_name", ""))
    latest, installed = parse_version(tag), parse_version(current)
    if latest is None or installed is None or latest <= installed:
        return None
    return Update(version=tag.lstrip("v"), url=str(release.get("html_url", "")))
