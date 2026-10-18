import pytest

from src.engine.maturity import payer_phase


@pytest.mark.parametrize(
    "approved_count, relationship_days, expected",
    [
        (0, 0, 0),
        (0, 400, 0),
        (1, 0, 1),
        (4, 400, 1),
        (5, 29.9, 1),
        (5, 30, 2),
        (40, 400, 2),
    ],
)
def test_payer_phase(approved_count, relationship_days, expected):
    assert payer_phase(approved_count, relationship_days) == expected
