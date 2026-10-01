import tomllib
from pathlib import Path

import pytest

from plaudertaste.config import Config, ConfigError, load_config, parse_config, render_default_config


def test_missing_file_is_created_with_defaults(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "config.toml"

    config = load_config(path)

    assert config == Config()
    assert path.exists()
    assert load_config(path) == Config()


def test_default_file_is_valid_toml_with_comments() -> None:
    text = render_default_config()

    assert "# Taste(n), die zum Sprechen gehalten werden" in text
    assert tomllib.loads(text) == {
        "hotkey": "ctrl_r",
        "language": "de",
        "model": "auto",
        "device": "auto",
    }


def test_partial_file_keeps_defaults_for_missing_keys(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('model = "small"\n', encoding="utf-8")

    assert load_config(path) == Config(model="small")


def test_values_are_stripped() -> None:
    assert parse_config({"hotkey": "  f9 "}).hotkey == "f9"


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"modell": "small"}, "Unbekannte Einträge: modell"),
        ({"model": "huge"}, "Unbekanntes Modell 'huge'"),
        ({"device": "gpu"}, "Unbekanntes Gerät 'gpu'"),
        ({"hotkey": ""}, "'hotkey' darf nicht leer sein"),
        ({"language": " "}, "'language' darf nicht leer sein"),
        ({"hotkey": 5}, "'hotkey' muss ein Text"),
    ],
)
def test_invalid_values_raise_clear_errors(data: dict[str, object], message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        parse_config(data)


def test_broken_toml_raises_config_error(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('model = "small', encoding="utf-8")

    with pytest.raises(ConfigError, match="Fehler in"):
        load_config(path)
