import pytest

from plaudertaste.repetitions import remove_repeated_sentences


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Schleife: dreimal und öfter derselbe Satz -> einmal
        (
            "Das ist gut. Und dann geht's, was ich meine. Und dann geht's, was ich meine. "
            "Und dann geht's, was ich meine.",
            "Das ist gut. Und dann geht's, was ich meine.",
        ),
        # Satzzeichen und Groß-/Kleinschreibung zählen nicht als Unterschied
        (
            "Wir sehen uns morgen. wir sehen uns morgen! Wir sehen uns morgen?",
            "Wir sehen uns morgen.",
        ),
        # zweimal kann Absicht sein -> bleibt
        (
            "Bitte noch mal prüfen. Bitte noch mal prüfen.",
            "Bitte noch mal prüfen. Bitte noch mal prüfen.",
        ),
        # kurze Sätze bleiben, auch dreifach
        ("Ja. Ja. Ja.", "Ja. Ja. Ja."),
        # nicht direkt hintereinander -> bleibt
        (
            "Das war gut. Wirklich. Das war gut. Wirklich. Das war gut.",
            "Das war gut. Wirklich. Das war gut. Wirklich. Das war gut.",
        ),
        ("Ganz normaler Text ohne Schleife.", "Ganz normaler Text ohne Schleife."),
        ("", ""),
    ],
)
def test_remove_repeated_sentences(text: str, expected: str) -> None:
    assert remove_repeated_sentences(text) == expected
