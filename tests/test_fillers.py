import pytest

from plaudertaste.fillers import remove_fillers


@pytest.mark.parametrize(
    ("whisper", "expected"),
    [
        # Echte Whisper-Ausgaben (gemessen): "eh" mitten im Satz bleibt bewusst stehen.
        (
            "Ich wollte dir eh nur sagen, dass wir eh morgen, ehm, also gegen 8 Uhr kommen. "
            "Hm, passt das?",
            "Ich wollte dir eh nur sagen, dass wir eh morgen, also gegen 8 Uhr kommen. Passt das?",
        ),
        (
            "Ich wollte dir eh nur sagen, dass wir im Morgen, ehm, also gegen 8 Uhr kommen.",
            "Ich wollte dir eh nur sagen, dass wir im Morgen, also gegen 8 Uhr kommen.",
        ),
    ],
)
def test_real_whisper_outputs(whisper: str, expected: str) -> None:
    assert remove_fillers(whisper) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ich wollte dir äh nur sagen", "Ich wollte dir nur sagen"),
        ("Ähm, das ist so.", "Das ist so."),
        ("Hallo, ähm, wie geht's?", "Hallo, wie geht's?"),
        ("Das passt ähm.", "Das passt."),
        ("Also ähhm das hmmm geht.", "Also das geht."),  # gedehnte Laute
        ("Eh, wo war ich?", "Wo war ich?"),  # "eh" mit Komma = Füllwort
        ("Ich komme, eh, später.", "Ich komme, später."),
        ("Das mache ich eh morgen.", "Das mache ich eh morgen."),  # "eh" = sowieso
        ("Eh egal.", "Eh egal."),
        ("Das mache ich eh.", "Das mache ich eh."),  # "eh" am Satzende = sowieso
        ("Das mache ich eh, keine Sorge.", "Das mache ich eh, keine Sorge."),
        ("Mhm, verstanden.", "Verstanden."),
        ("Das Ehepaar hm kommt.", "Das Ehepaar kommt."),  # nur ganze Wörter
        ("Ohne Füllwörter.", "Ohne Füllwörter."),
        ("und dann kommt er", "und dann kommt er"),  # keine Großschreibung ohne Grund
        ("ähm, und dann", "Und dann"),
        ("Ähm.", ""),  # nur Füllwörter -> kein Text
    ],
)
def test_rules(text: str, expected: str) -> None:
    assert remove_fillers(text) == expected
