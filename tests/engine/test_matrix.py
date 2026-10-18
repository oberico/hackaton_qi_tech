import pytest

from src.engine.engine import evaluate
from src.engine.risk_context import Decision, DecisionBasis, RiskLevel, RuleOutcome
from tests.engine.conftest import local_datetime, make_context

OK = RiskLevel.OK
SUSPICIOUS = RiskLevel.SUSPICIOUS
CRITICAL = RiskLevel.CRITICAL
APPROVED = Decision.APPROVED
TWO_FACTOR = Decision.TWO_FACTOR_REQUIRED
REJECTED = Decision.REJECTED

NIGHT_LIMIT = "HOW_NIGHT_LIMIT_EXCEEDED"
DESTINATION_NEW_ACCOUNT = "WHERE_DESTINATION_NEW_ACCOUNT"
UNKNOWN_PARTICIPANT = "WHERE_UNKNOWN_PARTICIPANT"
DESTINATION_FAN_IN = "WHERE_DESTINATION_FAN_IN"
DESTINATION_REJECTIONS = "WHERE_DESTINATION_REJECTIONS"
FLOOR_UNREGISTERED_DEVICE = "FLOOR_UNREGISTERED_DEVICE"
FLOOR_NIGHT_LIMIT = "FLOOR_NIGHT_LIMIT"

MATRIX_CELLS = {
    "all_ok": ((OK, OK, OK), APPROVED, DecisionBasis.CLEAN),
    "who_suspicious": ((SUSPICIOUS, OK, OK), TWO_FACTOR, DecisionBasis.SINGLE_SUSPICIOUS_AXIS),
    "how_suspicious": ((OK, SUSPICIOUS, OK), TWO_FACTOR, DecisionBasis.SINGLE_SUSPICIOUS_AXIS),
    "where_suspicious": ((OK, OK, SUSPICIOUS), TWO_FACTOR, DecisionBasis.SINGLE_SUSPICIOUS_AXIS),
    "who_how_suspicious": ((SUSPICIOUS, SUSPICIOUS, OK), REJECTED, DecisionBasis.TWO_SUSPICIOUS_AXES),
    "who_where_suspicious": ((SUSPICIOUS, OK, SUSPICIOUS), REJECTED, DecisionBasis.TWO_SUSPICIOUS_AXES),
    "how_where_suspicious": ((OK, SUSPICIOUS, SUSPICIOUS), REJECTED, DecisionBasis.TWO_SUSPICIOUS_AXES),
    "three_suspicious": ((SUSPICIOUS, SUSPICIOUS, SUSPICIOUS), REJECTED, DecisionBasis.TWO_SUSPICIOUS_AXES),
    "who_critical": ((CRITICAL, OK, OK), REJECTED, DecisionBasis.CRITICAL_AXIS),
    "how_critical": ((OK, CRITICAL, OK), REJECTED, DecisionBasis.CRITICAL_AXIS),
    "where_critical": ((OK, OK, CRITICAL), REJECTED, DecisionBasis.CRITICAL_AXIS),
    "critical_wins_over_suspicious": ((CRITICAL, SUSPICIOUS, SUSPICIOUS), REJECTED, DecisionBasis.CRITICAL_AXIS),
}


@pytest.mark.parametrize("levels, decision, basis", MATRIX_CELLS.values(), ids=MATRIX_CELLS.keys())
def test_matrix_cell(stub_axes, levels, decision, basis):
    stub_axes(*levels)

    result = evaluate(make_context())

    assert (result.who.level, result.how.level, result.where.level) == levels
    assert (result.decision, result.decision_basis) == (decision, basis)


NIGHT_PIX = {"amount": 150000, "transaction_date": local_datetime(22, 15)}
NEW_DESTINATION = {"destination_account_age_days": 7}
UNLISTED_PARTICIPANT = {"destination_participant_listed": False}

REAL_RULE_CELLS = {
    "night_limit_alone": ({**NIGHT_PIX}, (OK, SUSPICIOUS, OK), [NIGHT_LIMIT], [], TWO_FACTOR, DecisionBasis.SINGLE_SUSPICIOUS_AXIS),
    "new_destination_alone": ({**NEW_DESTINATION}, (OK, OK, SUSPICIOUS), [], [DESTINATION_NEW_ACCOUNT], TWO_FACTOR, DecisionBasis.SINGLE_SUSPICIOUS_AXIS),
    "unlisted_participant_alone": (
        {**UNLISTED_PARTICIPANT}, (OK, OK, SUSPICIOUS), [], [UNKNOWN_PARTICIPANT], TWO_FACTOR, DecisionBasis.SINGLE_SUSPICIOUS_AXIS,
    ),
    "night_limit_and_new_destination": (
        {**NIGHT_PIX, **NEW_DESTINATION}, (OK, SUSPICIOUS, SUSPICIOUS), [NIGHT_LIMIT], [DESTINATION_NEW_ACCOUNT],
        REJECTED, DecisionBasis.TWO_SUSPICIOUS_AXES,
    ),
    "night_limit_and_unlisted_participant": (
        {**NIGHT_PIX, **UNLISTED_PARTICIPANT}, (OK, SUSPICIOUS, SUSPICIOUS), [NIGHT_LIMIT], [UNKNOWN_PARTICIPANT],
        REJECTED, DecisionBasis.TWO_SUSPICIOUS_AXES,
    ),
    "both_where_rules_stay_one_suspicious_axis": (
        {**NEW_DESTINATION, **UNLISTED_PARTICIPANT}, (OK, OK, SUSPICIOUS), [], [DESTINATION_NEW_ACCOUNT, UNKNOWN_PARTICIPANT],
        TWO_FACTOR, DecisionBasis.SINGLE_SUSPICIOUS_AXIS,
    ),
}


@pytest.mark.parametrize(
    "transaction, levels, how_codes, where_codes, decision, basis", REAL_RULE_CELLS.values(), ids=REAL_RULE_CELLS.keys()
)
def test_first_pix_cell_with_real_rules(transaction, levels, how_codes, where_codes, decision, basis):
    result = evaluate(make_context(transaction=transaction))

    assert result.maturity_phase == 0
    assert (result.who.level, result.how.level, result.where.level) == levels
    assert [reason.code for reason in result.how.rules] == how_codes
    assert [reason.code for reason in result.where.rules] == where_codes
    assert (result.decision, result.decision_basis) == (decision, basis)


CRITICAL_WHERE_CELLS = {
    "rejections_alone": ({}, {"rejections_from_distinct_payers_24h": 2}, (OK, OK, CRITICAL), [], [DESTINATION_REJECTIONS]),
    "fan_in_on_new_destination": (
        {**NEW_DESTINATION}, {"distinct_payers_24h": 3}, (OK, OK, CRITICAL), [], [DESTINATION_NEW_ACCOUNT, DESTINATION_FAN_IN],
    ),
    "critical_where_wins_over_suspicious_how": (
        {**NIGHT_PIX}, {"rejections_from_distinct_payers_24h": 2}, (OK, SUSPICIOUS, CRITICAL), [NIGHT_LIMIT], [DESTINATION_REJECTIONS],
    ),
}


@pytest.mark.parametrize(
    "transaction, destination, levels, how_codes, where_codes", CRITICAL_WHERE_CELLS.values(), ids=CRITICAL_WHERE_CELLS.keys()
)
def test_first_pix_is_rejected_by_critical_evidence_from_the_destination(transaction, destination, levels, how_codes, where_codes):
    result = evaluate(make_context(transaction=transaction, destination=destination))

    assert result.maturity_phase == 0
    assert (result.who.level, result.how.level, result.where.level) == levels
    assert [reason.code for reason in result.how.rules] == how_codes
    assert [reason.code for reason in result.where.rules] == where_codes
    assert (result.decision, result.decision_basis) == (REJECTED, DecisionBasis.CRITICAL_AXIS)


def test_absence_of_history_is_never_evidence():
    result = evaluate(make_context())

    codes = [rule.code for rule in result.evaluated_rules]
    assert len(codes) == len(set(codes))
    assert all(rule.outcome != RuleOutcome.FIRED for rule in result.evaluated_rules)
    assert (result.who.level, result.how.level, result.where.level) == (OK, OK, OK)
    assert (result.decision, result.decision_basis) == (APPROVED, DecisionBasis.CLEAN)
    assert (result.maturity_phase, result.floors, result.trust_signals) == (0, [], [])


FLOOR_CELLS = {
    "floor_never_softens_two_suspicious_axes": (
        None, {**NIGHT_PIX, **NEW_DESTINATION}, {}, REJECTED, DecisionBasis.TWO_SUSPICIOUS_AXES,
        [FLOOR_UNREGISTERED_DEVICE, FLOOR_NIGHT_LIMIT],
    ),
    "critical_axis_prevails_over_the_device_floor": (
        (OK, OK, CRITICAL), {"amount": 50000}, {}, REJECTED, DecisionBasis.CRITICAL_AXIS, [FLOOR_UNREGISTERED_DEVICE],
    ),
    "device_floor_alone_never_rejects": (
        None, {"amount": 5000000}, {"unknown_device_amount_today": 5000000}, TWO_FACTOR, DecisionBasis.REGULATORY_FLOOR,
        [FLOOR_UNREGISTERED_DEVICE],
    ),
}


@pytest.mark.parametrize("levels, transaction, payer, decision, basis, floors", FLOOR_CELLS.values(), ids=FLOOR_CELLS.keys())
def test_regulatory_floor_only_lifts_an_approval(stub_axes, levels, transaction, payer, decision, basis, floors):
    if levels is not None:
        stub_axes(*levels)

    result = evaluate(make_context(transaction=transaction, payer=payer))

    assert (result.decision, result.decision_basis) == (decision, basis)
    assert result.floors == floors
