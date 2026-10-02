import pytest
from PySide6.QtCore import QPointF

from plaudertaste.charts import AreaChart, nice_ceiling, smooth_path


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 10), (7, 10), (11, 20), (20, 20), (21, 50), (180, 200), (1234, 2000), (5000, 5000)],
)
def test_nice_ceiling(value: float, expected: int) -> None:
    assert nice_ceiling(value) == expected


def test_smooth_curve_never_overshoots_neighbouring_values() -> None:
    # Spitze zwischen zwei Nullwerten: eine naive Kurve schösse unter die Nulllinie
    points = [QPointF(0, 100), QPointF(10, 100), QPointF(20, 0), QPointF(30, 100), QPointF(40, 100)]

    bounds = smooth_path(points).boundingRect()

    assert bounds.top() >= 0
    assert bounds.bottom() <= 100


@pytest.mark.usefixtures("qapp")
@pytest.mark.parametrize("values", [[0, 0, 0], [3, 0, 120, 45], [5]])
def test_chart_paints_with_and_without_data(values: list[int]) -> None:
    chart = AreaChart("Noch keine Diktate.")
    chart.resize(500, 220)
    chart.set_data([str(i) for i in range(len(values))], values)

    assert not chart.grab().isNull()
