import pytest

from plaudertaste.dictionary import Dictionary, Replacement
from plaudertaste.dictionary_page import DictionaryPage

pytestmark = pytest.mark.usefixtures("qapp")


def make_page() -> tuple[DictionaryPage, list[Dictionary]]:
    page = DictionaryPage()
    changes: list[Dictionary] = []
    page.changed.connect(changes.append)
    return page, changes


def test_add_and_remove_term() -> None:
    page, changes = make_page()

    page.term_input.setText("  Vujicic ")
    page.term_input.returnPressed.emit()
    assert changes[-1].terms == ("Vujicic",)
    assert page.term_input.text() == ""

    page.term_list.setCurrentRow(0)
    page.remove_term_button.click()
    assert changes[-1].terms == ()


def test_duplicate_term_is_not_reported_as_change() -> None:
    page, changes = make_page()
    page.set_dictionary(Dictionary(terms=("Plaudertaste",)))

    page.term_input.setText("plaudertaste")
    page.term_input.returnPressed.emit()

    assert changes == []


def test_add_replacement() -> None:
    page, changes = make_page()

    page.spoken_input.setText("mfg")
    page.spoken_input.returnPressed.emit()  # zweites Feld noch leer -> nur weiterspringen
    assert changes == []
    page.written_input.setPlainText("Mit freundlichen Grüßen")
    page.spoken_input.returnPressed.emit()

    assert changes[-1].replacements == (Replacement("mfg", "Mit freundlichen Grüßen"),)
    assert page.replacement_table.rowCount() == 1


def test_multiline_snippet_is_shown_on_one_row() -> None:
    page, changes = make_page()
    page.spoken_input.setText("meine Signatur")
    page.written_input.setPlainText("Viele Grüße\nSenad Vujicic")

    page.spoken_input.returnPressed.emit()

    assert changes[-1].replacements[0].written == "Viele Grüße\nSenad Vujicic"
    assert page.replacement_table.item(0, 1).text() == "Viele Grüße ⏎ Senad Vujicic"


def test_remove_replacement() -> None:
    page, changes = make_page()
    page.set_dictionary(
        Dictionary(replacements=(Replacement("mfg", "MfG"), Replacement("lg", "LG")))
    )

    page.replacement_table.selectRow(1)
    page.remove_replacement_button.click()

    assert changes[-1].replacements == (Replacement("mfg", "MfG"),)


def test_remove_buttons_need_a_selection() -> None:
    page, _ = make_page()
    page.set_dictionary(Dictionary(terms=("A",), replacements=(Replacement("x", "y"),)))

    assert not page.remove_term_button.isEnabled()
    assert not page.remove_replacement_button.isEnabled()


def test_too_many_terms_show_hint() -> None:
    page, _ = make_page()

    page.set_dictionary(Dictionary(terms=tuple(f"Begriff{i}" for i in range(200))))

    assert not page.terms_hint.isHidden()
