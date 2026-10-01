import os
from collections.abc import Iterator

import pytest

# Qt ohne echten Bildschirm: Tests sollen keine Fenster auf dem Monitor öffnen.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402  (erst nach QT_QPA_PLATFORM)


@pytest.fixture(scope="session")
def qapp() -> Iterator[QApplication]:
    """Eine QApplication für Tests, die Qt-Grafik (Icons, Fenster) brauchen."""
    app = QApplication.instance() or QApplication([])
    yield app  # type: ignore[misc]
