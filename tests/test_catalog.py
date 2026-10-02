import pytest
from faster_whisper import available_models

from plaudertaste.catalog import format_size, language_name, language_options, model_label
from plaudertaste.config import VALID_MODELS
from plaudertaste.models import MODELS, ModelInfo

pytestmark = pytest.mark.usefixtures("qapp")


def test_language_list_starts_with_auto_german_english() -> None:
    options = language_options()

    assert options[:3] == (("auto", "Automatisch erkennen"), ("de", "Deutsch"), ("en", "English"))


def test_language_list_covers_all_whisper_languages() -> None:
    """Schlägt Alarm, falls faster-whisper seine (interne) Sprachliste ändert."""
    codes = [code for code, _ in language_options()]

    assert len(codes) == len(set(codes)) == 101  # 100 Sprachen + automatisch
    assert {"de", "en", "fr", "bs", "tr", "jw"} <= set(codes)


@pytest.mark.parametrize(
    ("code", "name"),
    [("de", "Deutsch (German)"), ("fr", "Français (French)"), ("jw", "Jawa (Javanese)")],
)
def test_language_name(code: str, name: str) -> None:
    assert language_name(code) == name


def test_all_listed_models_exist_in_faster_whisper_and_config() -> None:
    names = {info.name for info in MODELS}

    assert names <= set(available_models())
    assert names | {"auto"} == VALID_MODELS


def test_model_label() -> None:
    info = ModelInfo("small", "Systran/faster-whisper-small", 486, "schnell, gut für CPU")

    assert model_label(info, downloaded=False) == "small – 486 MB, schnell, gut für CPU"
    assert model_label(info, downloaded=True).endswith("✓ heruntergeladen")


@pytest.mark.parametrize(
    ("mb", "text"), [(78, "78 MB"), (486, "486 MB"), (1622, "1,6 GB"), (3091, "3,1 GB")]
)
def test_format_size(mb: int, text: str) -> None:
    assert format_size(mb) == text


def test_repo_ids_match_faster_whisper() -> None:
    """Wir laden selbst herunter – es muss exakt dasselbe Modell sein wie bei faster-whisper."""
    from faster_whisper.utils import _MODELS  # intern, deshalb nur hier im Test

    assert {info.name: info.repo_id for info in MODELS} == {
        info.name: _MODELS[info.name] for info in MODELS
    }
