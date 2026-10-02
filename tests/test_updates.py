import pytest

from plaudertaste.updates import Update, check_for_update, parse_version, release_page


@pytest.mark.parametrize(
    ("text", "expected"),
    [("v1.2.3", (1, 2, 3)), ("0.10.0", (0, 10, 0)), (" v2 ", (2,)), ("beta", None), ("", None)],
)
def test_parse_version(text: str, expected: tuple[int, ...] | None) -> None:
    assert parse_version(text) == expected


def release(tag: str) -> dict[str, object]:
    return {"tag_name": tag, "html_url": f"https://github.com/x/y/releases/tag/{tag}"}


def test_newer_version_is_reported() -> None:
    update = check_for_update("0.9.0", "x/y", fetch=lambda repo: release("v0.10.0"))

    assert update == Update("0.10.0", "https://github.com/x/y/releases/tag/v0.10.0")


@pytest.mark.parametrize("tag", ["v0.1.0", "v0.0.9", "nightly"])
def test_same_older_or_unknown_version_is_ignored(tag: str) -> None:
    assert check_for_update("0.1.0", "x/y", fetch=lambda repo: release(tag)) is None


def test_offline_is_not_an_error() -> None:
    def offline(repo: str) -> dict[str, object]:
        raise OSError("Keine Verbindung")

    assert check_for_update("0.1.0", "x/y", fetch=offline) is None


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://github.com/senad-vujicic/plaudertaste/releases/tag/v0.2.0",
            "https://github.com/senad-vujicic/plaudertaste/releases/tag/v0.2.0",
        ),
        # fremde oder kaputte Adressen werden nie übernommen
        (
            "https://evil.example/plaudertaste",
            "https://github.com/senad-vujicic/plaudertaste/releases/latest",
        ),
        (
            "https://github.com/senad-vujicic/plaudertaste.evil/releases/x",
            "https://github.com/senad-vujicic/plaudertaste/releases/latest",
        ),
        (None, "https://github.com/senad-vujicic/plaudertaste/releases/latest"),
    ],
)
def test_release_page_only_accepts_own_project(url: object, expected: str) -> None:
    assert release_page("senad-vujicic/plaudertaste", url) == expected
