import pytest

from plaudertaste.voice_commands import apply_voice_commands


@pytest.mark.parametrize(
    ("whisper", "expected"),
    [
        # Echte Whisper-Ausgaben (gemessen mit large-v3-turbo und small):
        (
            "Hallo Jens, wie geht es dir? Neuer Absatz, ich wollte dir nur kurz Bescheid geben.",
            "Hallo Jens, wie geht es dir?\n\nIch wollte dir nur kurz Bescheid geben.",
        ),
        (
            "Hallo Jens Komma, wie geht es dir Fragezeichen, neue Absatz ich wollte dir nur "
            "kurz Bescheid geben, Punkt.",
            "Hallo Jens, wie geht es dir?\n\nIch wollte dir nur kurz Bescheid geben, Punkt.",
        ),
        (
            "Einkaufsliste Doppelpunkt neue Zeile Milch neue Zeile Brot neue Zeile Eier",
            "Einkaufsliste:\nMilch\nBrot\nEier",
        ),
        (
            "Einkaufsliste Doppelpunkt Neue Zeile Milch Neue Zeile Brot Neue Zeile Eier",
            "Einkaufsliste:\nMilch\nBrot\nEier",
        ),
        (
            "Der wichtigste Punkt ist Komma, dass wir pünktlich sind Ausrufezeichen.",
            "Der wichtigste Punkt ist, dass wir pünktlich sind!",  # "Punkt" bleibt ein Wort
        ),
    ],
)
def test_real_whisper_outputs(whisper: str, expected: str) -> None:
    assert apply_voice_commands(whisper) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ganz normaler Satz.", "Ganz normaler Satz."),
        ("Der Kommandant kommt.", "Der Kommandant kommt."),  # nur ganze Wörter
        ("Bescheid. Neuer Absatz. Wie geht's?", "Bescheid.\n\nWie geht's?"),  # Satzende bleibt
        ("Kommst du Fragezeichen ja", "Kommst du? Ja"),
        ("Zeile eins neue Zeile Zeile zwei", "Zeile eins\nZeile zwei"),
        ("Hallo neuen Absatz Tschüss", "Hallo\n\nTschüss"),
    ],
)
def test_edge_cases(text: str, expected: str) -> None:
    assert apply_voice_commands(text) == expected
