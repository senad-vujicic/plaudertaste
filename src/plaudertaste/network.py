"""Netzwerk-Wächter: protokolliert jede Verbindung von Plaudertaste – und blockiert sie
im Offline-Modus.

Er klinkt sich in Pythons Namensauflösung (getaddrinfo) und Verbindungsaufbau
(socket.connect) ein. Darüber läuft jede Verbindung des Hauptprozesses, egal aus welcher
Bibliothek. Verbindungen innerhalb des eigenen Rechners (localhost) sind nie betroffen.

Grenze, offen dokumentiert: Der Modell-Download läuft in einem eigenen Prozess, den der
Wächter nicht von innen sieht. Im Offline-Modus wird dieser Prozess gar nicht gestartet;
online trägt ihn record() selbst ins Protokoll ein.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger(__name__)

# Bekannte Gegenstellen -> verständlicher Zweck fürs Protokoll
_PURPOSES = (
    ("api.github.com", "Update-Prüfung"),
    ("huggingface.co", "Modell-Download"),
    ("hf.co", "Modell-Download"),
)


class OfflineError(OSError):
    """Verbindung im Offline-Modus blockiert."""


@dataclass(frozen=True)
class Connection:
    host: str
    purpose: str
    blocked: bool
    time: datetime = field(default_factory=datetime.now)


def purpose_of(host: str) -> str:
    for suffix, purpose in _PURPOSES:
        if host == suffix or host.endswith("." + suffix):
            return purpose
    return "unbekannt"


def is_local(host: str) -> bool:
    if host.lower() in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


class NetworkGuard:
    def __init__(self) -> None:
        self.offline = False
        self._connections: list[Connection] = []
        self._listeners: list[Callable[[Connection], None]] = []
        self._lock = threading.Lock()
        self._originals: tuple[object, object, object] | None = None

    @property
    def connections(self) -> list[Connection]:
        with self._lock:
            return list(self._connections)

    def subscribe(self, listener: Callable[[Connection], None]) -> None:
        """Wird bei jeder neuen Verbindung aufgerufen – aus dem Thread, der sie aufbaut."""
        self._listeners.append(listener)

    def record(self, host: str, purpose: str | None = None, blocked: bool = False) -> Connection:
        connection = Connection(host, purpose or purpose_of(host), blocked)
        with self._lock:
            # Mehrfache Anfragen an dieselbe Adresse (z. B. pro Datei) nur einmal anzeigen
            if any(
                c.host == host and c.blocked == blocked and c.purpose == connection.purpose
                for c in self._connections
            ):
                return connection
            self._connections.append(connection)
        log.info(
            "Netzwerk: %s %s (%s)",
            "BLOCKIERT" if blocked else "Verbindung zu",
            host,
            connection.purpose,
        )
        for listener in self._listeners:
            listener(connection)
        return connection

    def check(self, host: str) -> None:
        """Protokolliert eine Verbindung nach außen und blockiert sie im Offline-Modus."""
        if is_local(host):
            return
        self.record(host, blocked=self.offline)
        if self.offline:
            raise OfflineError(f"Offline-Modus: Verbindung zu {host} blockiert")

    def install(self) -> None:
        """Klinkt sich in socket ein. Einmal beim Programmstart aufrufen."""
        if self._originals is not None:
            return
        original_getaddrinfo = socket.getaddrinfo
        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex
        guard = self

        def getaddrinfo(host, *args, **kwargs):  # type: ignore[no-untyped-def]
            if isinstance(host, (str, bytes)):
                guard.check(host.decode() if isinstance(host, bytes) else host)
            return original_getaddrinfo(host, *args, **kwargs)

        def _address_host(address: object) -> str | None:
            if isinstance(address, tuple) and address and isinstance(address[0], str):
                return address[0]
            return None  # z. B. Unix-Sockets – kein Netzwerk nach außen

        def connect(sock, address):  # type: ignore[no-untyped-def]
            host = _address_host(address)
            if host is not None:
                guard._check_connect(host)
            return original_connect(sock, address)

        def connect_ex(sock, address):  # type: ignore[no-untyped-def]
            host = _address_host(address)
            if host is not None:
                guard._check_connect(host)
            return original_connect_ex(sock, address)

        self._originals = (original_getaddrinfo, original_connect, original_connect_ex)
        socket.getaddrinfo = getaddrinfo  # type: ignore[assignment]
        socket.socket.connect = connect  # type: ignore[method-assign]
        socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]

    def uninstall(self) -> None:
        if self._originals is None:
            return
        socket.getaddrinfo, socket.socket.connect, socket.socket.connect_ex = self._originals  # type: ignore[assignment,method-assign]
        self._originals = None

    def _check_connect(self, host: str) -> None:
        # Der Name wurde meist schon bei getaddrinfo protokolliert; hier kommt nur die
        # IP-Adresse an. Online also nichts doppelt eintragen, offline aber hart blockieren.
        if is_local(host) or not self.offline:
            return
        self.record(host, blocked=True)
        raise OfflineError(f"Offline-Modus: Verbindung zu {host} blockiert")


guard = NetworkGuard()  # eine Instanz für das ganze Programm
