from datetime import timedelta

import pytest

from src.engine.engine import evaluate
from src.engine.risk_context import Decision, DecisionBasis, DeviceTrust, RiskLevel, RuleOutcome
from tests.engine.conftest import local_datetime, make_context, rule_of

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


TRANSACTION_MOMENT = local_datetime(14)
TWO_FACTOR_BY_AXIS = (Decision.TWO_FACTOR_REQUIRED, DecisionBasis.SINGLE_SUSPICIOUS_AXIS)
APPROVED_BY_TRUST = (Decision.APPROVED, DecisionBasis.TRUST_DOWNGRADE)
RECURRENT_THRESHOLD = {"approved_count": 2, "first_approved_hours_ago": 24}

RECURRENT_BENEFICIARY_BORDERS = {
    "two_approved_and_first_older_than_24h": (2, timedelta(hours=25), True, 25.0),
    "one_approved_is_not_recurrent": (1, timedelta(hours=48), False, 48.0),
    "exactly_24h_is_not_old_enough": (2, timedelta(hours=24), False, 24.0),
    "one_minute_past_24h_is_old_enough": (2, timedelta(hours=24, minutes=1), True, 24.02),
    "no_approved_pix_to_the_beneficiary": (0, None, False, None),
}


@pytest.mark.parametrize(
    "approved_count, first_approved_age, fires, hours_ago", RECURRENT_BENEFICIARY_BORDERS.values(), ids=RECURRENT_BENEFICIARY_BORDERS.keys()
)
def test_recurrent_beneficiary_border(approved_count, first_approved_age, fires, hours_ago):
    first_approved_at = None if first_approved_age is None else TRANSACTION_MOMENT - first_approved_age
    context = make_context(
        transaction={"destination_account_age_days": 10},
        payer={"device_trust": DeviceTrust.TRUSTED},
        beneficiary={"approved_count": approved_count, "first_approved_at": first_approved_at},
    )

    result = evaluate(context)

    rule = rule_of(result, SIGNAL)
    assert rule.axis == "trust"
    assert rule.outcome == (RuleOutcome.FIRED if fires else RuleOutcome.NOT_FIRED)
    assert rule.level is None
    assert rule.observed == {"approved_count": approved_count, "first_approved_hours_ago": hours_ago}
    assert rule.threshold == RECURRENT_THRESHOLD
    assert rule.description and rule.translation
    assert result.trust_signals == ([SIGNAL] if fires else [])
    assert (result.decision, result.decision_basis) == (APPROVED_BY_TRUST if fires else TWO_FACTOR_BY_AXIS)


SELF_PIX_THRESHOLD = {"same_owner": True, "destination_account_age_days": 30, "device_trust": "trusted"}

MATURE_SELF_PIX_BORDERS = {
    "self_pix_to_mature_account_from_trusted_device": (True, 400, DeviceTrust.TRUSTED, True, APPROVED_BY_TRUST),
    "destination_with_exactly_30_days_is_mature": (True, 30, DeviceTrust.TRUSTED, True, APPROVED_BY_TRUST),
    "destination_with_29_days_is_not_mature": (
        True, 29, DeviceTrust.TRUSTED, False, (Decision.REJECTED, DecisionBasis.TWO_SUSPICIOUS_AXES),
    ),
    "different_owner_is_not_self_pix": (False, 400, DeviceTrust.TRUSTED, False, TWO_FACTOR_BY_AXIS),
    "observing_device_is_not_trusted": (True, 400, DeviceTrust.OBSERVING, False, TWO_FACTOR_BY_AXIS),
}


@pytest.mark.parametrize(
    "same_owner, destination_age_days, device_trust, fires, decision", MATURE_SELF_PIX_BORDERS.values(), ids=MATURE_SELF_PIX_BORDERS.keys()
)
def test_mature_self_pix_border(same_owner, destination_age_days, device_trust, fires, decision):
    context = make_context(
        transaction={"same_owner": same_owner, "destination_account_age_days": destination_age_days},
        payer={"device_trust": device_trust, "transactions_last_10min": 3},
    )

    result = evaluate(context)

    rule = rule_of(result, SECOND_SIGNAL)
    assert rule.axis == "trust"
    assert rule.outcome == (RuleOutcome.FIRED if fires else RuleOutcome.NOT_FIRED)
    assert rule.level is None
    assert rule.observed == {
        "same_owner": same_owner,
        "destination_account_age_days": destination_age_days,
        "device_trust": device_trust.value,
    }
    assert rule.threshold == SELF_PIX_THRESHOLD
    assert result.trust_signals == ([SECOND_SIGNAL] if fires else [])
    assert (result.decision, result.decision_basis) == decision


def test_recurrent_beneficiary_never_downgrades_a_critical_axis():
    context = make_context(
        payer={"device_trust": DeviceTrust.TRUSTED},
        destination={"distinct_payers_24h": 1, "rejections_from_distinct_payers_24h": 2},
        beneficiary={"approved_count": 5, "first_approved_at": TRANSACTION_MOMENT - timedelta(days=10)},
    )

    result = evaluate(context)

    assert rule_of(result, SIGNAL).outcome == RuleOutcome.FIRED
    assert result.where.level == CRITICAL
    assert result.trust_signals == []
    assert (result.decision, result.decision_basis) == (Decision.REJECTED, DecisionBasis.CRITICAL_AXIS)
