from pathlib import Path

import pytest

from plaudertaste.dictionary import (
    MAX_HINT_CHARS,
    Dictionary,
    DictionaryError,
    Replacement,
    load_dictionary,
    save_dictionary,
)

MFG = Replacement("mfg", "Mit freundlichen Grüßen")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Danke und mfg", "Danke und Mit freundlichen Grüßen"),
        ("Danke und MFG.", "Danke und Mit freundlichen Grüßen."),  # Groß/klein egal, Satzzeichen bleibt
        ("Mfg, Senad", "Mit freundlichen Grüßen, Senad"),
        ("mfgx ist kein Treffer", "mfgx ist kein Treffer"),  # nur ganze Wörter
        ("Ohne Kürzel", "Ohne Kürzel"),
    ],
)
def test_replacements_whole_words_ignoring_case(text: str, expected: str) -> None:
    assert Dictionary(replacements=(MFG,)).apply(text) == expected


def test_multi_word_replacement_tolerates_spacing() -> None:
    dictionary = Dictionary(replacements=(Replacement("meine Adresse", "Hauptstraße 1, 85049 Ingolstadt"),))

    assert dictionary.apply("Schick es an Meine   adresse bitte") == (
        "Schick es an Hauptstraße 1, 85049 Ingolstadt bitte"
    )


def test_longer_replacements_win() -> None:
    dictionary = Dictionary(
        replacements=(Replacement("lg", "Liebe Grüße"), Replacement("lg lg", "Ganz liebe Grüße"))
    )

    assert dictionary.apply("lg lg") == "Ganz liebe Grüße"


def test_special_characters_in_replacement_are_literal() -> None:
    dictionary = Dictionary(replacements=(Replacement("pfad", r"C:\Users\1"),))

    assert dictionary.apply("pfad") == r"C:\Users\1"


def test_hotwords() -> None:
    assert Dictionary().hotwords() is None
    assert Dictionary(terms=("Plaudertaste", "Vujicic")).hotwords() == "Plaudertaste, Vujicic"


def test_too_many_terms_are_detected() -> None:
    many = Dictionary(terms=tuple(f"Begriff{i}" for i in range(MAX_HINT_CHARS // 5)))

    assert many.hint_too_long()
    assert not Dictionary(terms=("Plaudertaste",)).hint_too_long()


def test_editing_keeps_entries_unique() -> None:
    dictionary = Dictionary().with_term("Plaudertaste").with_term(" plaudertaste ").with_term("")

    assert dictionary.terms == ("Plaudertaste",)
    assert dictionary.without_term("Plaudertaste").terms == ()

    dictionary = Dictionary().with_replacement("mfg", "MfG").with_replacement("MFG", "Mit freundlichen Grüßen")
    assert dictionary.replacements == (Replacement("MFG", "Mit freundlichen Grüßen"),)
    assert dictionary.with_replacement("leer", " ").replacements == dictionary.replacements
    assert dictionary.without_replacement("MFG").replacements == ()


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "woerterbuch.toml"
    dictionary = Dictionary(terms=("Plaudertaste", "Karosseriebau"), replacements=(MFG,))

    save_dictionary(path, dictionary)

    assert load_dictionary(path) == dictionary
    assert path.read_text(encoding="utf-8").startswith("# Plaudertaste – eigenes Wörterbuch")


def test_missing_file_means_empty_dictionary(tmp_path: Path) -> None:
    assert load_dictionary(tmp_path / "gibt-es-nicht.toml") == Dictionary()


@pytest.mark.parametrize(
    "content",
    ['terms = ["ok", 5]', '[[replacements]]\nspoken = "mfg"', "terms = [kaputt"],
)
def test_broken_file_raises_clear_error(tmp_path: Path, content: str) -> None:
    path = tmp_path / "woerterbuch.toml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(DictionaryError):
        load_dictionary(path)
