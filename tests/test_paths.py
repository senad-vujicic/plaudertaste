from pathlib import Path

import pytest

from plaudertaste import paths


def test_paths_follow_windows_folders(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))

    assert paths.config_file() == tmp_path / "Roaming" / "Plaudertaste" / "config.toml"
    assert paths.log_dir() == tmp_path / "Local" / "Plaudertaste" / "logs"
    assert paths.lock_file() == tmp_path / "Local" / "Plaudertaste" / "plaudertaste.lock"


def test_fallback_without_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert paths.config_dir() == Path.home() / ".config" / "Plaudertaste"
