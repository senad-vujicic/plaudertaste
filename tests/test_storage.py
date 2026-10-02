from pathlib import Path

import pytest

from plaudertaste import storage
from plaudertaste.storage import write_text_atomic


def test_writes_and_replaces(tmp_path: Path) -> None:
    path = tmp_path / "neu" / "datei.toml"

    write_text_atomic(path, "erste")
    write_text_atomic(path, "zweite – mit Umlaut ä")

    assert path.read_text(encoding="utf-8") == "zweite – mit Umlaut ä"
    assert list(path.parent.iterdir()) == [path]  # keine Zwischendatei übrig


def test_crash_while_writing_keeps_old_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "woerterbuch.toml"
    write_text_atomic(path, "altes Wörterbuch")

    def crash(*args: object) -> None:
        raise OSError("Stromausfall")

    monkeypatch.setattr(storage.os, "replace", crash)
    with pytest.raises(OSError):
        write_text_atomic(path, "neues Wörterbuch")

    assert path.read_text(encoding="utf-8") == "altes Wörterbuch"
