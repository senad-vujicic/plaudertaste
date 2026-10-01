from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> Iterator[QApplication]:
    """Eine QApplication für Tests, die Qt-Grafik (Icons, Pixmaps) brauchen."""
    app = QApplication.instance() or QApplication([])
    yield app  # type: ignore[misc]
