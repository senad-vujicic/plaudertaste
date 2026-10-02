"""Zwischenablage über die Windows-API – mit Datenschutz-Markierungen.

Plaudertaste fügt Text über die Zwischenablage ein (Strg+V). Ohne Markierung speichert
Windows jeden diktierten Text im Zwischenablage-Verlauf (Win+V) und lädt ihn – wenn
"Geräteübergreifend synchronisieren" an ist – in die Microsoft-Cloud hoch. Deshalb legt
Plaudertaste zusätzlich die von Microsoft dafür dokumentierten Formate ab, wie es auch
Passwort-Manager tun:
https://learn.microsoft.com/windows/win32/dataxchg/clipboard-formats#cloud-clipboard-and-clipboard-history-formats
"""

from __future__ import annotations

import ctypes
import time
from collections.abc import Iterator
from contextlib import contextmanager
from ctypes import wintypes

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
HWND_MESSAGE = wintypes.HWND(-3)  # unsichtbares Nur-Nachrichten-Fenster
OPEN_ATTEMPTS = 25  # ein anderes Programm kann die Zwischenablage kurz belegt halten
OPEN_RETRY_S = 0.01

_DWORD_ZERO = (0).to_bytes(4, "little")
PRIVACY_FORMATS: dict[str, bytes] = {
    # Schließt den Inhalt von Verlauf, Cloud-Sync und Zwischenablage-Überwachung aus.
    "ExcludeClipboardContentFromMonitorProcessing": b"\x01",
    "CanIncludeInClipboardHistory": _DWORD_ZERO,  # 0 = nicht in den Verlauf (Win+V)
    "CanUploadToCloudClipboard": _DWORD_ZERO,  # 0 = nicht in die Cloud
    "Clipboard Viewer Ignore": b"\x01",  # Konvention von Programmen wie Ditto
}

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

for _name, _restype, _argtypes in (
    ("OpenClipboard", wintypes.BOOL, [wintypes.HWND]),
    ("CloseClipboard", wintypes.BOOL, []),
    ("EmptyClipboard", wintypes.BOOL, []),
    ("GetClipboardData", wintypes.HANDLE, [wintypes.UINT]),
    ("SetClipboardData", wintypes.HANDLE, [wintypes.UINT, wintypes.HANDLE]),
    ("IsClipboardFormatAvailable", wintypes.BOOL, [wintypes.UINT]),
    ("RegisterClipboardFormatW", wintypes.UINT, [wintypes.LPCWSTR]),
    (
        "CreateWindowExW",
        wintypes.HWND,
        [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        + [ctypes.c_int] * 4
        + [wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID],
    ),
    ("DestroyWindow", wintypes.BOOL, [wintypes.HWND]),
):
    _function = getattr(_user32, _name)
    _function.restype, _function.argtypes = _restype, _argtypes

for _name, _restype, _argtypes in (
    ("GlobalAlloc", wintypes.HGLOBAL, [wintypes.UINT, ctypes.c_size_t]),
    ("GlobalLock", wintypes.LPVOID, [wintypes.HGLOBAL]),
    ("GlobalUnlock", wintypes.BOOL, [wintypes.HGLOBAL]),
    ("GlobalFree", wintypes.HGLOBAL, [wintypes.HGLOBAL]),
    ("GlobalSize", ctypes.c_size_t, [wintypes.HGLOBAL]),
):
    _function = getattr(_kernel32, _name)
    _function.restype, _function.argtypes = _restype, _argtypes


class ClipboardError(OSError):
    """Die Zwischenablage ließ sich nicht lesen oder beschreiben."""


@contextmanager
def _opened() -> Iterator[None]:
    # Windows verlangt ein Fenster als Besitzer – sonst scheitert SetClipboardData.
    window = _user32.CreateWindowExW(
        0, "STATIC", None, 0, 0, 0, 0, 0, HWND_MESSAGE, None, None, None
    )
    if not window:
        raise ClipboardError(ctypes.get_last_error(), "Hilfsfenster nicht erstellbar")
    try:
        for _ in range(OPEN_ATTEMPTS):
            if _user32.OpenClipboard(window):
                break
            time.sleep(OPEN_RETRY_S)
        else:
            raise ClipboardError("Die Zwischenablage ist von einem anderen Programm belegt.")
        try:
            yield
        finally:
            _user32.CloseClipboard()
    finally:
        _user32.DestroyWindow(window)


def _put(clipboard_format: int, data: bytes) -> None:
    handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        raise ClipboardError(ctypes.get_last_error(), "Kein Speicher für die Zwischenablage")
    pointer = _kernel32.GlobalLock(handle)
    ctypes.memmove(pointer, data, len(data))
    _kernel32.GlobalUnlock(handle)
    if not _user32.SetClipboardData(clipboard_format, handle):
        _kernel32.GlobalFree(handle)  # nur bei Fehler: sonst gehört der Speicher Windows
        raise ClipboardError(ctypes.get_last_error(), "Zwischenablage nicht beschreibbar")


class WindowsClipboard:
    def paste(self) -> str:
        """Text in der Zwischenablage – leer, wenn dort kein Text liegt (z. B. ein Bild)."""
        with _opened():
            if not _user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                return ""
            handle = _user32.GetClipboardData(CF_UNICODETEXT)
            pointer = _kernel32.GlobalLock(handle) if handle else None
            if not pointer:
                return ""
            try:
                characters = _kernel32.GlobalSize(handle) // 2
                return ctypes.wstring_at(pointer, characters).split("\0", 1)[0]
            finally:
                _kernel32.GlobalUnlock(handle)

    def copy(self, text: str) -> None:
        """Legt Text privat ab: nicht im Verlauf, nicht in der Cloud."""
        with _opened():
            if not _user32.EmptyClipboard():
                raise ClipboardError(ctypes.get_last_error(), "Zwischenablage nicht leerbar")
            _put(CF_UNICODETEXT, (text + "\0").encode("utf-16-le"))
            for name, value in PRIVACY_FORMATS.items():
                _put(_user32.RegisterClipboardFormatW(name), value)
