import pytest

from src.engine.engine import evaluate
from src.engine.risk_context import Decision, DecisionBasis, DeviceTrust, RiskLevel
from tests.engine.conftest import local_datetime, make_context

OK = RiskLevel.OK
SUSPICIOUS = RiskLevel.SUSPICIOUS
CRITICAL = RiskLevel.CRITICAL
SIGNAL = "TRUST_RECURRENT_BENEFICIARY"
SECOND_SIGNAL = "TRUST_MATURE_SELF_PIX"

TRUST_CELLS = {
    "downgrades_the_only_suspicious_axis": (
        (OK, SUSPICIOUS, OK), [SIGNAL], (OK, OK, OK), [SIGNAL], Decision.APPROVED, DecisionBasis.TRUST_DOWNGRADE,
    ),
    "downgrades_where_alone": (
        (OK, OK, SUSPICIOUS), [SIGNAL], (OK, OK, OK), [SIGNAL], Decision.APPROVED, DecisionBasis.TRUST_DOWNGRADE,
    ),
    "downgrades_how_before_where": (
        (OK, SUSPICIOUS, SUSPICIOUS), [SIGNAL], (OK, OK, SUSPICIOUS), [SIGNAL],
        Decision.TWO_FACTOR_REQUIRED, DecisionBasis.TRUST_DOWNGRADE,
    ),
    "downgrades_who_before_where": (
        (SUSPICIOUS, OK, SUSPICIOUS), [SIGNAL], (OK, OK, SUSPICIOUS), [SIGNAL],
        Decision.TWO_FACTOR_REQUIRED, DecisionBasis.TRUST_DOWNGRADE,
    ),
    "two_signals_still_downgrade_one_axis": (
        (OK, SUSPICIOUS, SUSPICIOUS), [SIGNAL, SECOND_SIGNAL], (OK, OK, SUSPICIOUS), [SIGNAL],
        Decision.TWO_FACTOR_REQUIRED, DecisionBasis.TRUST_DOWNGRADE,
    ),
    "never_downgrades_critical_who": (
        (CRITICAL, OK, OK), [SIGNAL], (CRITICAL, OK, OK), [], Decision.REJECTED, DecisionBasis.CRITICAL_AXIS,
    ),
    "never_downgrades_critical_how": (
        (OK, CRITICAL, OK), [SIGNAL], (OK, CRITICAL, OK), [], Decision.REJECTED, DecisionBasis.CRITICAL_AXIS,
    ),
    "never_downgrades_critical_where": (
        (OK, OK, CRITICAL), [SIGNAL], (OK, OK, CRITICAL), [], Decision.REJECTED, DecisionBasis.CRITICAL_AXIS,
    ),
    "keeps_critical_while_downgrading_a_suspicious_axis": (
        (OK, SUSPICIOUS, CRITICAL), [SIGNAL], (OK, OK, CRITICAL), [SIGNAL], Decision.REJECTED, DecisionBasis.CRITICAL_AXIS,
    ),
    "no_signal_keeps_the_levels": (
        (OK, SUSPICIOUS, OK), [], (OK, SUSPICIOUS, OK), [], Decision.TWO_FACTOR_REQUIRED, DecisionBasis.SINGLE_SUSPICIOUS_AXIS,
    ),
    "signal_without_suspicious_axis_is_not_applied": (
        (OK, OK, OK), [SIGNAL], (OK, OK, OK), [], Decision.APPROVED, DecisionBasis.CLEAN,
    ),
}


@pytest.mark.parametrize(
    "levels, signals, trusted_levels, applied, decision, basis", TRUST_CELLS.values(), ids=TRUST_CELLS.keys()
)
def test_trust_downgrade_cell(stub_axes, stub_trust_signals, levels, signals, trusted_levels, applied, decision, basis):
    stub_axes(*levels)
    stub_trust_signals(signals)

    result = evaluate(make_context(payer={"device_trust": DeviceTrust.TRUSTED}))

    assert (result.who.level, result.how.level, result.where.level) == trusted_levels
    assert result.trust_signals == applied
    assert (result.decision, result.decision_basis) == (decision, basis)


def test_downgrade_keeps_the_reason_and_the_night_floor_still_requires_two_factor(stub_trust_signals):
    stub_trust_signals([SIGNAL])

    result = evaluate(
        make_context(
            transaction={"amount": 150000, "transaction_date": local_datetime(22, 15)},
            payer={"device_trust": DeviceTrust.TRUSTED},
        )
    )

    assert result.how.level == OK
    assert [reason.code for reason in result.how.rules] == ["HOW_NIGHT_LIMIT_EXCEEDED"]
    assert result.trust_signals == [SIGNAL]
    assert result.floors == ["FLOOR_NIGHT_LIMIT"]
    assert (result.decision, result.decision_basis) == (Decision.TWO_FACTOR_REQUIRED, DecisionBasis.REGULATORY_FLOOR)
