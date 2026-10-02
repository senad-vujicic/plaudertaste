import socket
import urllib.request
from collections.abc import Iterator

import pytest

from plaudertaste.network import NetworkGuard, OfflineError, is_local, purpose_of


@pytest.fixture
def guard() -> Iterator[NetworkGuard]:
    guard = NetworkGuard()
    guard.install()
    yield guard
    guard.uninstall()


@pytest.mark.parametrize(
    ("host", "local"),
    [
        ("localhost", True),
        ("127.0.0.1", True),
        ("::1", True),
        ("api.github.com", False),
        ("192.0.2.1", False),
    ],
)
def test_is_local(host: str, local: bool) -> None:
    assert is_local(host) is local


@pytest.mark.parametrize(
    ("host", "purpose"),
    [
        ("api.github.com", "Update-Prüfung"),
        ("huggingface.co", "Modell-Download"),
        ("cdn-lfs.hf.co", "Modell-Download"),
        ("example.com", "unbekannt"),
    ],
)
def test_purpose_of(host: str, purpose: str) -> None:
    assert purpose_of(host) == purpose


def test_offline_blocks_name_lookup_before_any_network(guard: NetworkGuard) -> None:
    guard.offline = True

    with pytest.raises(OfflineError):
        socket.getaddrinfo("api.github.com", 443)

    assert [(c.host, c.blocked, c.purpose) for c in guard.connections] == [
        ("api.github.com", True, "Update-Prüfung")
    ]


def test_offline_blocks_direct_ip_connection(guard: NetworkGuard) -> None:
    guard.offline = True
    sock = socket.socket()
    try:
        with pytest.raises(OfflineError):
            sock.connect(("192.0.2.1", 443))  # Testadresse, wird nie wirklich angefragt
    finally:
        sock.close()


def test_offline_blocks_real_library_calls(guard: NetworkGuard) -> None:
    """Auch Bibliotheken (hier urllib, wie beim Update-Check) kommen nicht durch."""
    guard.offline = True

    with pytest.raises(Exception) as caught:
        urllib.request.urlopen("https://api.github.com/", timeout=2)

    assert "Offline-Modus" in str(caught.value)


def test_localhost_is_never_blocked(guard: NetworkGuard) -> None:
    guard.offline = True
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    client = socket.socket()
    try:
        client.connect(server.getsockname())  # darf nicht blockiert werden
    finally:
        client.close()
        server.close()

    assert guard.connections == []


def test_online_records_but_allows(guard: NetworkGuard) -> None:
    seen: list[str] = []
    guard.subscribe(lambda connection: seen.append(connection.host))

    guard.check("api.github.com")  # wirft nicht
    guard.check("api.github.com")  # doppelt -> nur einmal im Protokoll

    assert [(c.host, c.blocked) for c in guard.connections] == [("api.github.com", False)]
    assert seen == ["api.github.com"]


def test_uninstall_restores_socket(guard: NetworkGuard) -> None:
    patched = socket.getaddrinfo
    guard.uninstall()

    assert socket.getaddrinfo is not patched  # Original wieder eingesetzt
    assert socket.getaddrinfo.__module__ == "socket"
