import pytest

from src.engine.matrix import decide
from src.engine.risk_context import Decision, DecisionBasis, RiskLevel

OK = RiskLevel.OK
SUSPICIOUS = RiskLevel.SUSPICIOUS
CRITICAL = RiskLevel.CRITICAL


def test_all_axes_ok_is_approved_clean():
    assert decide(OK, OK, OK) == (Decision.APPROVED, DecisionBasis.CLEAN)


@pytest.mark.parametrize("levels", [(SUSPICIOUS, OK, OK), (OK, SUSPICIOUS, OK), (OK, OK, SUSPICIOUS)])
def test_single_suspicious_axis_requires_two_factor(levels):
    assert decide(*levels) == (Decision.TWO_FACTOR_REQUIRED, DecisionBasis.SINGLE_SUSPICIOUS_AXIS)


@pytest.mark.parametrize("levels", [(SUSPICIOUS, SUSPICIOUS, OK), (SUSPICIOUS, OK, SUSPICIOUS), (OK, SUSPICIOUS, SUSPICIOUS)])
def test_two_suspicious_axes_is_rejected(levels):
    assert decide(*levels) == (Decision.REJECTED, DecisionBasis.TWO_SUSPICIOUS_AXES)


def test_three_suspicious_axes_is_rejected_for_two_suspicious_axes():
    assert decide(SUSPICIOUS, SUSPICIOUS, SUSPICIOUS) == (Decision.REJECTED, DecisionBasis.TWO_SUSPICIOUS_AXES)


@pytest.mark.parametrize("levels", [(CRITICAL, OK, OK), (OK, CRITICAL, OK), (OK, OK, CRITICAL)])
def test_critical_axis_alone_is_rejected(levels):
    assert decide(*levels) == (Decision.REJECTED, DecisionBasis.CRITICAL_AXIS)


def test_critical_wins_over_suspicious_basis():
    assert decide(CRITICAL, SUSPICIOUS, SUSPICIOUS) == (Decision.REJECTED, DecisionBasis.CRITICAL_AXIS)
