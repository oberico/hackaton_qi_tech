from datetime import timedelta

import pytest

from src.engine import policy
from src.engine.engine import evaluate
from src.engine.risk_context import Decision, DecisionBasis, DeviceTrust, Flow, PersonType, RiskLevel, RuleOutcome
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
    "destination_fractional_age_is_reported_with_two_decimals": (
        "WHERE_DESTINATION_NEW_ACCOUNT", {"destination_account_age_days": 7.552083333333333}, True,
        {"destination_account_age_days": 7.55}, {"destination_account_age_days": 30},
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


REJECTED_BY_CRITICAL_AXIS = (Decision.REJECTED, DecisionBasis.CRITICAL_AXIS)

FAN_IN_BORDERS = {
    "pf_pf_two_payers": (Flow.PF_PF, 7, 2, False, 3),
    "pf_pf_three_payers": (Flow.PF_PF, 7, 3, True, 3),
    "pf_pj_nine_payers": (Flow.PF_PJ, 7, 9, False, 10),
    "pf_pj_ten_payers": (Flow.PF_PJ, 7, 10, True, 10),
    "pj_pf_two_payers": (Flow.PJ_PF, 7, 2, False, 3),
    "pj_pf_three_payers": (Flow.PJ_PF, 7, 3, True, 3),
    "pj_pj_nine_payers": (Flow.PJ_PJ, 7, 9, False, 10),
    "pj_pj_ten_payers": (Flow.PJ_PJ, 7, 10, True, 10),
    "destination_twenty_nine_days_old": (Flow.PF_PF, 29, 3, True, 3),
    "destination_exactly_thirty_days_old": (Flow.PF_PF, 30, 3, False, 3),
    "mature_destination_with_many_payers": (Flow.PF_PF, 400, 50, False, 3),
}


def expected_without_fan_in(destination_age_days):
    return TWO_FACTOR_BY_AXIS if destination_age_days < 30 else APPROVED


@pytest.mark.parametrize("flow, destination_age_days, payers, fires, threshold_payers", FAN_IN_BORDERS.values(), ids=FAN_IN_BORDERS.keys())
def test_destination_fan_in_border(flow, destination_age_days, payers, fires, threshold_payers):
    context = make_context(
        transaction={"flow": flow, "destination_account_age_days": destination_age_days},
        destination={"distinct_payers_24h": payers},
    )

    result = evaluate(context)

    rule = rule_of(result, "WHERE_DESTINATION_FAN_IN")
    assert (rule.outcome, rule.observed, rule.threshold) == (
        RuleOutcome.FIRED if fires else RuleOutcome.NOT_FIRED,
        {"distinct_payers_24h": payers, "destination_account_age_days": destination_age_days},
        {"distinct_payers_24h": threshold_payers, "destination_account_age_days": 30},
    )
    assert (rule.axis, rule.level) == ("where", RiskLevel.CRITICAL if fires else None)
    assert rule.description and rule.translation
    assert [reason.code for reason in result.where.rules if reason.code == "WHERE_DESTINATION_FAN_IN"] == (
        ["WHERE_DESTINATION_FAN_IN"] if fires else []
    )
    assert (result.decision, result.decision_basis) == (REJECTED_BY_CRITICAL_AXIS if fires else expected_without_fan_in(destination_age_days))


REJECTIONS_BORDERS = {
    "no_rejections": (0, False),
    "one_rejecting_payer": (1, False),
    "two_rejecting_payers": (2, True),
    "many_rejecting_payers": (5, True),
}


@pytest.mark.parametrize("rejections, fires", REJECTIONS_BORDERS.values(), ids=REJECTIONS_BORDERS.keys())
def test_destination_rejections_border(rejections, fires):
    result = evaluate(make_context(destination={"rejections_from_distinct_payers_24h": rejections}))

    rule = rule_of(result, "WHERE_DESTINATION_REJECTIONS")
    assert (rule.outcome, rule.observed, rule.threshold) == (
        RuleOutcome.FIRED if fires else RuleOutcome.NOT_FIRED,
        {"rejections_from_distinct_payers_24h": rejections},
        {"rejections_from_distinct_payers_24h": 2},
    )
    assert (rule.axis, rule.level) == ("where", RiskLevel.CRITICAL if fires else None)
    assert rule.description and rule.translation
    assert [reason.code for reason in result.where.rules] == (["WHERE_DESTINATION_REJECTIONS"] if fires else [])
    assert (result.decision, result.decision_basis) == (REJECTED_BY_CRITICAL_AXIS if fires else APPROVED)


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


def test_new_account_texts_follow_the_policy_parameter(monkeypatch):
    monkeypatch.setattr(policy, "DESTINATION_NEW_ACCOUNT_DAYS", 45)

    result = evaluate(make_context(transaction={"destination_account_age_days": 40}))

    rule = rule_of(result, "WHERE_DESTINATION_NEW_ACCOUNT")
    assert rule.outcome == RuleOutcome.FIRED
    assert rule.threshold == {"destination_account_age_days": 45}
    assert "45" in rule.description
    assert "45" in rule.translation


DECISION_BY_LEVEL = {
    None: APPROVED,
    RiskLevel.SUSPICIOUS: TWO_FACTOR_BY_AXIS,
    RiskLevel.CRITICAL: (Decision.REJECTED, DecisionBasis.CRITICAL_AXIS),
}

VELOCITY_THRESHOLD = {
    Flow.PF_PF: {"suspicious": 3, "critical": 6},
    Flow.PJ_PF: {"suspicious": 20, "critical": 40},
}

VELOCITY_BORDERS = {
    "pf_pf_two_attempts": (Flow.PF_PF, 2, None),
    "pf_pf_three_attempts": (Flow.PF_PF, 3, RiskLevel.SUSPICIOUS),
    "pf_pf_five_attempts": (Flow.PF_PF, 5, RiskLevel.SUSPICIOUS),
    "pf_pf_six_attempts": (Flow.PF_PF, 6, RiskLevel.CRITICAL),
    "pj_pf_nineteen_attempts": (Flow.PJ_PF, 19, None),
    "pj_pf_twenty_attempts": (Flow.PJ_PF, 20, RiskLevel.SUSPICIOUS),
    "pj_pf_thirty_nine_attempts": (Flow.PJ_PF, 39, RiskLevel.SUSPICIOUS),
    "pj_pf_forty_attempts": (Flow.PJ_PF, 40, RiskLevel.CRITICAL),
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


DEVICE_COMPROMISED_THRESHOLD = {"distinct_documents_total": 3, "distinct_documents_24h": 2}

DEVICE_COMPROMISED_BORDERS = {
    "two_documents_in_total": (2, 0, None),
    "three_documents_in_total": (3, 0, RiskLevel.CRITICAL),
    "one_document_in_24h": (1, 1, None),
    "two_documents_in_24h": (2, 2, RiskLevel.CRITICAL),
    "two_in_total_and_one_in_24h": (2, 1, None),
    "three_in_total_and_two_in_24h": (3, 2, RiskLevel.CRITICAL),
}


@pytest.mark.parametrize("total, last_24h, level", DEVICE_COMPROMISED_BORDERS.values(), ids=DEVICE_COMPROMISED_BORDERS.keys())
def test_device_compromised_border(total, last_24h, level):
    context = make_context(device={"distinct_documents_total": total, "distinct_documents_24h": last_24h})

    result = evaluate(context)

    rule = rule_of(result, "WHO_DEVICE_COMPROMISED")
    assert (rule.outcome, rule.level) == (RuleOutcome.FIRED if level else RuleOutcome.NOT_FIRED, level)
    assert (rule.observed, rule.threshold) == (
        {"distinct_documents_total": total, "distinct_documents_24h": last_24h}, DEVICE_COMPROMISED_THRESHOLD,
    )
    assert rule.axis == "who"
    assert rule.description and rule.translation
    assert result.who.level == (level or RiskLevel.OK)
    assert (result.decision, result.decision_basis) == DECISION_BY_LEVEL[level]


CEILING_BORDERS = {
    "phase_zero_individual_exactly_the_reference": (300000, PersonType.INDIVIDUAL, 400, [], None, 300000),
    "phase_zero_individual_one_cent_above_the_reference": (300001, PersonType.INDIVIDUAL, 400, [], RiskLevel.SUSPICIOUS, 300000),
    "phase_zero_new_account_exactly_the_reference": (100000, PersonType.INDIVIDUAL, 89.9, [], None, 100000),
    "phase_zero_new_account_one_cent_above_the_reference": (100001, PersonType.INDIVIDUAL, 89.9, [], RiskLevel.SUSPICIOUS, 100000),
    "account_of_ninety_days_uses_the_mature_reference": (100001, PersonType.INDIVIDUAL, 90, [], None, 300000),
    "phase_zero_company_exactly_the_reference": (2000000, PersonType.COMPANY, 400, [], None, 2000000),
    "phase_zero_company_one_cent_above_the_reference": (2000001, PersonType.COMPANY, 400, [], RiskLevel.SUSPICIOUS, 2000000),
    "challenge_example_amount_is_below_the_cold_start_reference": (150000, PersonType.INDIVIDUAL, 400, [], None, 300000),
    "phase_one_exactly_the_blended_ceiling": (252500, PersonType.INDIVIDUAL, 400, [10000], None, 252500),
    "phase_one_one_cent_above_the_blended_ceiling": (252501, PersonType.INDIVIDUAL, 400, [10000], RiskLevel.SUSPICIOUS, 252500),
    "five_approved_exactly_the_blended_ceiling": (157500, PersonType.INDIVIDUAL, 400, [10000] * 5, None, 157500),
    "five_approved_one_cent_above_the_blended_ceiling": (157501, PersonType.INDIVIDUAL, 400, [10000] * 5, RiskLevel.SUSPICIOUS, 157500),
    "percentile_is_interpolated_over_the_sorted_amounts": (
        181500, PersonType.INDIVIDUAL, 400, [50000, 10000, 10000, 10000, 10000], None, 181500,
    ),
    "percentile_interpolated_one_cent_above": (
        181501, PersonType.INDIVIDUAL, 400, [10000, 10000, 50000, 10000, 10000], RiskLevel.SUSPICIOUS, 181500,
    ),
    "fractional_ceiling_is_truncated_to_whole_cents": (218571, PersonType.INDIVIDUAL, 400, [10000, 10001], None, 218571),
    "fractional_ceiling_one_cent_above": (218572, PersonType.INDIVIDUAL, 400, [10000, 10001], RiskLevel.SUSPICIOUS, 218571),
    "large_history_raises_the_ceiling_above_the_reference": (900000, PersonType.INDIVIDUAL, 400, [1000000] * 5, None, 900000),
    "large_history_one_cent_above_the_raised_ceiling": (900001, PersonType.INDIVIDUAL, 400, [1000000] * 5, RiskLevel.SUSPICIOUS, 900000),
    "company_history_exactly_the_blended_ceiling": (2500000, PersonType.COMPANY, 400, [2000000] * 5, None, 2500000),
    "company_history_one_cent_above_the_blended_ceiling": (2500001, PersonType.COMPANY, 400, [2000000] * 5, RiskLevel.SUSPICIOUS, 2500000),
}


@pytest.mark.parametrize(
    "amount, person_type, account_age_days, approved_amounts, level, ceiling", CEILING_BORDERS.values(), ids=CEILING_BORDERS.keys()
)
def test_customer_ceiling_border(amount, person_type, account_age_days, approved_amounts, level, ceiling):
    flow = Flow.PJ_PJ if person_type == PersonType.COMPANY else Flow.PF_PF
    context = make_context(
        transaction={
            "amount": amount, "source_person_type": person_type, "flow": flow, "source_account_age_days": account_age_days,
        },
        payer={
            "approved_count": len(approved_amounts), "approved_amounts_90d": approved_amounts, "relationship_days": 60,
            "device_trust": DeviceTrust.TRUSTED,
        },
    )

    result = evaluate(context)

    rule = rule_of(result, "HOW_ABOVE_CUSTOMER_CEILING")
    assert (rule.outcome, rule.level) == (RuleOutcome.FIRED if level else RuleOutcome.NOT_FIRED, level)
    assert (rule.observed, rule.threshold) == ({"amount": amount}, {"ceiling": ceiling})
    assert rule.axis == "how"
    assert rule.description and rule.translation
    assert (result.decision, result.decision_basis) == (TWO_FACTOR_BY_AXIS if level else APPROVED)


EARLY_MORNING_BORDERS = {
    "midnight_is_early_morning": (50000, local_datetime(0, 0), {}, 0, True),
    "five_fifty_nine_is_early_morning": (50000, local_datetime(5, 59), {}, 5, True),
    "six_hundred_is_day": (50000, local_datetime(6, 0), {}, 6, False),
    "twenty_three_fifty_nine_is_evening": (50000, local_datetime(23, 59), {}, 23, False),
    "fourteen_hundred_is_day": (50000, local_datetime(14, 0), {}, 14, False),
    "exactly_two_hundred_reais_does_not_fire": (20000, local_datetime(3, 0), {}, 3, False),
    "one_cent_above_two_hundred_reais_fires": (20001, local_datetime(3, 0), {}, 3, True),
    "exactly_one_thousand_reais_fires": (100000, local_datetime(3, 0), {}, 3, True),
    "one_cent_above_one_thousand_reais_is_left_to_the_night_limit": (100001, local_datetime(3, 0), {}, 3, False),
    "local_hour_comes_from_the_payer_offset": (50000, local_datetime(4, 0, utc_offset_minutes=0), {}, 1, True),
    "utc_early_morning_that_is_local_evening_does_not_fire": (50000, local_datetime(2, 0, utc_offset_minutes=0), {}, 23, False),
    "company_payer_is_also_covered": (50000, local_datetime(3, 0), {"flow": Flow.PJ_PJ}, 3, True),
}


@pytest.mark.parametrize(
    "amount, transaction_date, transaction, local_hour, fires", EARLY_MORNING_BORDERS.values(), ids=EARLY_MORNING_BORDERS.keys()
)
def test_early_morning_amount_border(amount, transaction_date, transaction, local_hour, fires):
    context = make_context(
        transaction={"amount": amount, "transaction_date": transaction_date, **transaction},
        payer={"device_trust": DeviceTrust.TRUSTED},
    )

    result = evaluate(context)

    rule = rule_of(result, "HOW_EARLY_MORNING_AMOUNT")
    assert (rule.outcome, rule.level) == (RuleOutcome.FIRED if fires else RuleOutcome.NOT_FIRED, RiskLevel.SUSPICIOUS if fires else None)
    assert rule.observed == {"amount": amount, "local_hour": local_hour}
    assert rule.threshold == {"min_amount": 20000, "max_amount": 100000}
    assert rule.axis == "how"
    assert rule.description and rule.translation
    assert [reason.code for reason in result.how.rules if reason.code == "HOW_EARLY_MORNING_AMOUNT"] == (
        ["HOW_EARLY_MORNING_AMOUNT"] if fires else []
    )
    if fires:
        assert (result.decision, result.decision_basis) == TWO_FACTOR_BY_AXIS


DEVICE_UNKNOWN_BORDERS = {
    "unknown_device_with_one_known_device": (DeviceTrust.UNKNOWN, 1, True),
    "unknown_device_with_many_known_devices": (DeviceTrust.UNKNOWN, 4, True),
    "unknown_device_without_known_devices_is_cold_start": (DeviceTrust.UNKNOWN, 0, False),
    "observing_device_with_known_devices": (DeviceTrust.OBSERVING, 2, False),
    "trusted_device_with_known_devices": (DeviceTrust.TRUSTED, 2, False),
}


@pytest.mark.parametrize("device_trust, known_devices, fires", DEVICE_UNKNOWN_BORDERS.values(), ids=DEVICE_UNKNOWN_BORDERS.keys())
def test_device_unknown_border(device_trust, known_devices, fires):
    result = evaluate(make_context(payer={"device_trust": device_trust, "known_devices_count": known_devices}))

    rule = rule_of(result, "WHO_DEVICE_UNKNOWN")
    assert (rule.outcome, rule.level) == (RuleOutcome.FIRED if fires else RuleOutcome.NOT_FIRED, RiskLevel.SUSPICIOUS if fires else None)
    assert rule.observed == {"device_trust": device_trust.value, "known_devices_count": known_devices}
    assert rule.threshold == {"known_devices_count": 1}
    assert rule.axis == "who"
    assert rule.description and rule.translation
    assert result.who.level == (RiskLevel.SUSPICIOUS if fires else RiskLevel.OK)
    assert (result.decision, result.decision_basis) == (TWO_FACTOR_BY_AXIS if fires else APPROVED)


RETRY_BORDERS = {
    "smaller_amount_one_second_inside_the_window": (599, 100000, 50000, True, 9),
    "smaller_amount_exactly_ten_minutes_later": (600, 100000, 50000, False, 10),
    "smaller_amount_one_minute_later": (60, 100000, 50000, True, 1),
    "one_cent_smaller_amount": (60, 100000, 99999, True, 1),
    "same_amount_is_not_a_probe": (60, 100000, 100000, False, 1),
    "larger_amount_is_not_a_probe": (60, 100000, 100001, False, 1),
    "rejection_twenty_minutes_ago": (1200, 100000, 50000, False, 20),
    "no_previous_rejection": (None, None, 50000, False, None),
    "rejection_after_the_pix_under_analysis_is_ignored": (-60, 100000, 50000, False, -1),
}


@pytest.mark.parametrize(
    "seconds_since, rejected_amount, amount, fires, minutes_since", RETRY_BORDERS.values(), ids=RETRY_BORDERS.keys()
)
def test_retry_after_rejection_border(seconds_since, rejected_amount, amount, fires, minutes_since):
    base = make_context()
    rejection_at = None if seconds_since is None else base.transaction.transaction_date - timedelta(seconds=seconds_since)
    context = make_context(
        transaction={"amount": amount},
        payer={"last_rejection_at": rejection_at, "last_rejected_amount": rejected_amount, "device_trust": DeviceTrust.TRUSTED},
    )

    result = evaluate(context)

    rule = rule_of(result, "HOW_RETRY_AFTER_REJECTION")
    assert (rule.outcome, rule.level) == (RuleOutcome.FIRED if fires else RuleOutcome.NOT_FIRED, RiskLevel.SUSPICIOUS if fires else None)
    if seconds_since is None:
        assert (rule.observed, rule.threshold) == (None, None)
    else:
        assert rule.observed == {"minutes_since_rejection": minutes_since, "amount": amount, "last_rejected_amount": rejected_amount}
        assert rule.threshold == {"window_minutes": 10}
    assert rule.axis == "how"
    assert rule.description and rule.translation
    assert result.how.level == (RiskLevel.SUSPICIOUS if fires else RiskLevel.OK)
    assert (result.decision, result.decision_basis) == (TWO_FACTOR_BY_AXIS if fires else APPROVED)


TEST_PIX_THRESHOLD = {
    "test_max_amount": 1000,
    "followup_min_amount": 20000,
    "followup_multiplier": 20,
    "window_minutes": 15,
}

TEST_PIX_BORDERS = {
    "small_pix_then_exactly_two_hundred_reais": (True, 20000, None, True),
    "small_pix_then_one_cent_below_two_hundred_reais": (True, 19999, None, False),
    "small_pix_then_large_amount": (True, 100000, None, True),
    "no_small_pix_to_the_destination": (False, 100000, None, False),
    "destination_first_approved_by_the_test_pix_itself": (True, 100000, 5, True),
    "destination_first_approved_exactly_at_the_window_start": (True, 100000, 15, True),
    "destination_with_a_relationship_before_the_window_is_recurrent": (True, 100000, 16, False),
    "destination_approved_long_ago_is_recurrent": (True, 100000, 60 * 24 * 30, False),
}


@pytest.mark.parametrize(
    "small_amount_sent, amount, first_approved_minutes_ago, fires", TEST_PIX_BORDERS.values(), ids=TEST_PIX_BORDERS.keys()
)
def test_test_pix_border(small_amount_sent, amount, first_approved_minutes_ago, fires):
    moment = make_context().transaction.transaction_date
    first_approved_at = None if first_approved_minutes_ago is None else moment - timedelta(minutes=first_approved_minutes_ago)
    context = make_context(
        transaction={"amount": amount},
        payer={"small_amount_to_destination_last_15min": small_amount_sent, "device_trust": DeviceTrust.TRUSTED},
        beneficiary={
            "approved_count": 0 if first_approved_at is None else 1,
            "first_approved_at": first_approved_at,
        },
    )

    result = evaluate(context)

    rule = rule_of(result, "HOW_TEST_PIX")
    assert (rule.outcome, rule.level) == (RuleOutcome.FIRED if fires else RuleOutcome.NOT_FIRED, RiskLevel.SUSPICIOUS if fires else None)
    assert rule.observed == {"amount": amount, "small_amount_to_destination_last_15min": small_amount_sent}
    assert rule.threshold == TEST_PIX_THRESHOLD
    assert rule.axis == "how"
    assert rule.description and rule.translation
    assert (result.decision, result.decision_basis) == (TWO_FACTOR_BY_AXIS if fires else APPROVED)


WHO_AGGRAVATING_THRESHOLD = {
    "min_signals": 2,
    "ip_distinct_payers_1h": 5,
}

WHO_AGGRAVATING_BORDERS = {
    "no_aggravating_signals": (1, False, "app", ["app"], 1, False),
    "only_ip_private": (1, True, "app", ["app"], 1, False),
    "only_distinct_payers_five": (5, False, "app", ["app"], 1, False),
    "only_new_channel_with_history": (1, False, "web", ["app"], 1, False),
    "four_distinct_payers_with_private_ip_does_not_fire": (4, True, "app", ["app"], 1, False),
    "five_distinct_payers_with_private_ip_fires": (5, True, "app", ["app"], 1, True),
    "private_ip_with_new_channel_and_history_fires": (1, True, "web", ["app"], 1, True),
    "five_distinct_payers_with_new_channel_and_history_fires": (5, False, "web", ["app"], 1, True),
    "all_three_signals_fire": (5, True, "web", ["app"], 1, True),
    "new_channel_without_payer_history_does_not_count": (1, True, "web", [], 0, False),
}


@pytest.mark.parametrize(
    "distinct_payers_1h, ip_is_private, channel, known_channels, approved_count, fires",
    WHO_AGGRAVATING_BORDERS.values(),
    ids=WHO_AGGRAVATING_BORDERS.keys(),
)
def test_who_aggravating_signals_border(
    distinct_payers_1h, ip_is_private, channel, known_channels, approved_count, fires
):
    context = make_context(
        transaction={"channel": channel, "ip_is_private": ip_is_private},
        ip={"distinct_payers_1h": distinct_payers_1h},
        payer={"known_channels": known_channels, "approved_count": approved_count, "device_trust": DeviceTrust.TRUSTED},
    )

    result = evaluate(context)

    rule = rule_of(result, "WHO_AGGRAVATING_SIGNALS")
    expected_outcome = RuleOutcome.FIRED if fires else RuleOutcome.NOT_FIRED
    expected_level = RiskLevel.SUSPICIOUS if fires else None
    assert (rule.outcome, rule.level) == (expected_outcome, expected_level)
    assert rule.axis == "who"
    assert rule.threshold == WHO_AGGRAVATING_THRESHOLD
    assert rule.observed["signals_count"] >= (2 if fires else 0)
    assert rule.description and rule.translation
    assert (result.decision, result.decision_basis) == (TWO_FACTOR_BY_AXIS if fires else APPROVED)
