import pytest

from src.engine.engine import evaluate
from src.engine.risk_context import Decision, DecisionBasis, DeviceTrust, Flow, RiskLevel, RuleOutcome
from tests.engine.conftest import local_datetime, make_context, rule_of

APPROVED = (Decision.APPROVED, DecisionBasis.CLEAN)
TWO_FACTOR_BY_AXIS = (Decision.TWO_FACTOR_REQUIRED, DecisionBasis.SINGLE_SUSPICIOUS_AXIS)
TWO_FACTOR_BY_FLOOR = (Decision.TWO_FACTOR_REQUIRED, DecisionBasis.REGULATORY_FLOOR)

NIGHT_THRESHOLD = {"night_amount": 100000}

NIGHT_BORDERS = {
    "above_limit": (150000, 0, local_datetime(22, 15), {}, True, 150000),
    "sum_includes_the_pix_under_analysis": (50000, 60000, local_datetime(22, 15), {}, True, 110000),
    "exactly_the_limit_does_not_fire": (40000, 60000, local_datetime(22, 15), {}, False, 100000),
    "one_cent_above_the_limit_fires": (40001, 60000, local_datetime(22, 15), {}, True, 100001),
    "two_am_sums_since_eight_pm_of_the_previous_day": (20000, 90000, local_datetime(2, 0), {}, True, 110000),
    "nineteen_fifty_nine_is_day": (150000, 0, local_datetime(19, 59), {}, False, None),
    "twenty_hundred_is_night": (150000, 0, local_datetime(20, 0), {}, True, 150000),
    "five_fifty_nine_is_night": (150000, 0, local_datetime(5, 59), {}, True, 150000),
    "six_hundred_is_day": (150000, 0, local_datetime(6, 0), {}, False, None),
    "fourteen_hundred_is_day": (150000, 0, local_datetime(14, 0), {}, False, None),
    "local_hour_comes_from_the_payer_offset": (150000, 0, local_datetime(1, 15, utc_offset_minutes=0), {}, True, 150000),
    "self_pix_is_outside": (150000, 0, local_datetime(22, 15), {"same_owner": True}, False, None),
    "pf_pj_is_outside": (150000, 0, local_datetime(22, 15), {"flow": Flow.PF_PJ}, False, None),
    "pj_pf_is_outside": (150000, 0, local_datetime(22, 15), {"flow": Flow.PJ_PF}, False, None),
    "pj_pj_is_outside": (150000, 0, local_datetime(22, 15), {"flow": Flow.PJ_PJ}, False, None),
}


@pytest.mark.parametrize(
    "amount, prior, transaction_date, transaction, fires, night_amount", NIGHT_BORDERS.values(), ids=NIGHT_BORDERS.keys()
)
def test_night_limit_border(amount, prior, transaction_date, transaction, fires, night_amount):
    context = make_context(
        transaction={"amount": amount, "transaction_date": transaction_date, **transaction},
        payer={"night_amount_to_individuals": prior, "device_trust": DeviceTrust.TRUSTED},
    )

    result = evaluate(context)

    expected_outcome = RuleOutcome.FIRED if fires else RuleOutcome.NOT_FIRED
    expected_observed = None if night_amount is None else {"night_amount": night_amount}
    expected_threshold = None if night_amount is None else NIGHT_THRESHOLD
    for code in ("HOW_NIGHT_LIMIT_EXCEEDED", "FLOOR_NIGHT_LIMIT"):
        rule = rule_of(result, code)
        assert (rule.outcome, rule.observed, rule.threshold) == (expected_outcome, expected_observed, expected_threshold)
        assert rule.description and rule.translation
    assert rule_of(result, "HOW_NIGHT_LIMIT_EXCEEDED").level == (RiskLevel.SUSPICIOUS if fires else None)
    assert ("FLOOR_NIGHT_LIMIT" in result.floors) is fires
    assert (result.decision, result.decision_basis) == (TWO_FACTOR_BY_AXIS if fires else APPROVED)


DEVICE_THRESHOLD = {"amount": 20000, "daily_amount": 100000}

UNREGISTERED_DEVICE_BORDERS = {
    "one_cent_above_two_hundred_reais": (20001, 0, Flow.PF_PF, DeviceTrust.UNKNOWN, True, {"amount": 20001, "daily_amount": 20001}),
    "exactly_two_hundred_reais": (20000, 0, Flow.PF_PF, DeviceTrust.UNKNOWN, False, {"amount": 20000, "daily_amount": 20000}),
    "daily_sum_above_one_thousand_reais": (10000, 95000, Flow.PF_PF, DeviceTrust.UNKNOWN, True, {"amount": 10000, "daily_amount": 105000}),
    "daily_sum_exactly_one_thousand_reais": (10000, 90000, Flow.PF_PF, DeviceTrust.UNKNOWN, False, {"amount": 10000, "daily_amount": 100000}),
    "observing_device_is_registered": (50000, 0, Flow.PF_PF, DeviceTrust.OBSERVING, False, None),
    "trusted_device_is_registered": (50000, 0, Flow.PF_PF, DeviceTrust.TRUSTED, False, None),
    "company_payer_is_outside": (50000, 0, Flow.PJ_PF, DeviceTrust.UNKNOWN, False, None),
}


@pytest.mark.parametrize(
    "amount, today, flow, device_trust, fires, observed", UNREGISTERED_DEVICE_BORDERS.values(), ids=UNREGISTERED_DEVICE_BORDERS.keys()
)
def test_unregistered_device_floor_border(amount, today, flow, device_trust, fires, observed):
    context = make_context(
        transaction={"amount": amount, "flow": flow},
        payer={"unknown_device_amount_today": today, "device_trust": device_trust},
    )

    result = evaluate(context)

    rule = rule_of(result, "FLOOR_UNREGISTERED_DEVICE")
    expected_threshold = None if observed is None else DEVICE_THRESHOLD
    assert (rule.outcome, rule.observed, rule.threshold) == (
        RuleOutcome.FIRED if fires else RuleOutcome.NOT_FIRED, observed, expected_threshold,
    )
    assert rule.axis == "floor"
    assert result.floors == (["FLOOR_UNREGISTERED_DEVICE"] if fires else [])
    assert (result.decision, result.decision_basis) == (TWO_FACTOR_BY_FLOOR if fires else APPROVED)


WHERE_BORDERS = {
    "destination_twenty_nine_days_old": (
        "WHERE_DESTINATION_NEW_ACCOUNT", {"destination_account_age_days": 29}, True,
        {"destination_account_age_days": 29}, {"destination_account_age_days": 30},
    ),
    "destination_exactly_thirty_days_old": (
        "WHERE_DESTINATION_NEW_ACCOUNT", {"destination_account_age_days": 30}, False,
        {"destination_account_age_days": 30}, {"destination_account_age_days": 30},
    ),
    "participant_not_listed": (
        "WHERE_UNKNOWN_PARTICIPANT", {"destination_participant_listed": False}, True,
        {"destination_participant_listed": False}, {"destination_participant_listed": True},
    ),
    "participant_listed": (
        "WHERE_UNKNOWN_PARTICIPANT", {"destination_participant_listed": True}, False,
        {"destination_participant_listed": True}, {"destination_participant_listed": True},
    ),
}


@pytest.mark.parametrize("code, transaction, fires, observed, threshold", WHERE_BORDERS.values(), ids=WHERE_BORDERS.keys())
def test_where_rule_border(code, transaction, fires, observed, threshold):
    result = evaluate(make_context(transaction=transaction))

    rule = rule_of(result, code)
    assert (rule.outcome, rule.observed, rule.threshold) == (RuleOutcome.FIRED if fires else RuleOutcome.NOT_FIRED, observed, threshold)
    assert (rule.axis, rule.level) == ("where", RiskLevel.SUSPICIOUS if fires else None)
    assert rule.description and rule.translation
    assert [reason.code for reason in result.where.rules] == ([code] if fires else [])
    assert (result.decision, result.decision_basis) == (TWO_FACTOR_BY_AXIS if fires else APPROVED)


MATURITY_BORDERS = {
    "no_approved_pix": (0, 0, 0),
    "no_approved_pix_with_old_relationship": (0, 400, 0),
    "first_approved_pix": (1, 0, 1),
    "four_approved_pix": (4, 400, 1),
    "five_approved_pix_just_under_thirty_days": (5, 29.9, 1),
    "five_approved_pix_and_thirty_days": (5, 30, 2),
    "established_payer": (40, 400, 2),
}


@pytest.mark.parametrize("approved_count, relationship_days, phase", MATURITY_BORDERS.values(), ids=MATURITY_BORDERS.keys())
def test_payer_maturity_phase_border(approved_count, relationship_days, phase):
    context = make_context(payer={"approved_count": approved_count, "relationship_days": relationship_days})

    assert evaluate(context).maturity_phase == phase


DECISION_BY_LEVEL = {
    None: APPROVED,
    RiskLevel.SUSPICIOUS: TWO_FACTOR_BY_AXIS,
    RiskLevel.CRITICAL: (Decision.REJECTED, DecisionBasis.CRITICAL_AXIS),
}

VELOCITY_THRESHOLD = {Flow.PF_PF: {"suspicious": 3, "critical": 6}}

VELOCITY_BORDERS = {
    "pf_pf_two_attempts": (Flow.PF_PF, 2, None),
    "pf_pf_three_attempts": (Flow.PF_PF, 3, RiskLevel.SUSPICIOUS),
    "pf_pf_five_attempts": (Flow.PF_PF, 5, RiskLevel.SUSPICIOUS),
    "pf_pf_six_attempts": (Flow.PF_PF, 6, RiskLevel.CRITICAL),
}


@pytest.mark.parametrize("flow, attempts, level", VELOCITY_BORDERS.values(), ids=VELOCITY_BORDERS.keys())
def test_velocity_border(flow, attempts, level):
    context = make_context(transaction={"flow": flow}, payer={"transactions_last_10min": attempts})

    result = evaluate(context)

    rule = rule_of(result, "HOW_VELOCITY_EXCEEDED")
    assert (rule.outcome, rule.level) == (RuleOutcome.FIRED if level else RuleOutcome.NOT_FIRED, level)
    assert (rule.observed, rule.threshold) == ({"attempts": attempts}, VELOCITY_THRESHOLD[flow])
    assert rule.axis == "how"
    assert rule.description and rule.translation
    assert result.how.level == (level or RiskLevel.OK)
    assert (result.decision, result.decision_basis) == DECISION_BY_LEVEL[level]
