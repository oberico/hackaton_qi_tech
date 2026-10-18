import pytest

from src.engine.engine import evaluate
from src.engine.risk_context import Decision, Flow, RiskLevel, RuleOutcome

CODE = "HOW_NIGHT_LIMIT_EXCEEDED"


def rule_of(result):
    return next(rule for rule in result.evaluated_rules if rule.code == CODE)


def night_context(make_context, local_datetime, amount, hour=22, minute=15, prior=0, **transaction):
    return make_context(
        transaction={"amount": amount, "transaction_date": local_datetime(hour, minute), **transaction},
        payer={"night_amount_to_individuals": prior},
    )


def test_fires_above_limit_with_observed_and_threshold(make_context, local_datetime):
    result = evaluate(night_context(make_context, local_datetime, 150000))

    rule = rule_of(result)
    assert rule.outcome == RuleOutcome.FIRED
    assert rule.axis == "how"
    assert rule.level == RiskLevel.SUSPICIOUS
    assert rule.observed == {"night_amount": 150000}
    assert rule.threshold == {"night_amount": 100000}
    assert rule.description
    assert rule.translation
    assert result.how.level == RiskLevel.SUSPICIOUS
    assert [reason.code for reason in result.how.rules] == [CODE]


def test_sum_includes_the_pix_under_analysis(make_context, local_datetime):
    result = evaluate(night_context(make_context, local_datetime, 50000, prior=60000))

    assert rule_of(result).outcome == RuleOutcome.FIRED
    assert rule_of(result).observed == {"night_amount": 110000}


def test_exactly_the_limit_does_not_fire(make_context, local_datetime):
    result = evaluate(night_context(make_context, local_datetime, 40000, prior=60000))

    assert rule_of(result).outcome == RuleOutcome.NOT_FIRED
    assert result.how.level == RiskLevel.OK


def test_one_cent_above_the_limit_fires(make_context, local_datetime):
    result = evaluate(night_context(make_context, local_datetime, 40001, prior=60000))

    assert rule_of(result).outcome == RuleOutcome.FIRED


def test_pix_at_two_in_the_morning_sums_since_eight_pm_of_the_previous_day(make_context, local_datetime):
    result = evaluate(night_context(make_context, local_datetime, 20000, hour=2, minute=0, prior=90000))

    assert rule_of(result).outcome == RuleOutcome.FIRED
    assert rule_of(result).observed == {"night_amount": 110000}


@pytest.mark.parametrize("hour, minute, fires", [(19, 59, False), (20, 0, True), (5, 59, True), (6, 0, False), (14, 0, False)])
def test_night_period_boundaries(make_context, local_datetime, hour, minute, fires):
    result = evaluate(night_context(make_context, local_datetime, 150000, hour=hour, minute=minute))

    assert (rule_of(result).outcome == RuleOutcome.FIRED) is fires


def test_local_hour_comes_from_the_payer_offset(make_context, local_datetime):
    in_utc = local_datetime(1, 15, utc_offset_minutes=0)
    context = make_context(
        transaction={"amount": 150000, "transaction_date": in_utc, "utc_offset_minutes": -180},
    )

    assert rule_of(evaluate(context)).outcome == RuleOutcome.FIRED


def test_self_pix_is_outside_the_rule(make_context, local_datetime):
    result = evaluate(night_context(make_context, local_datetime, 150000, same_owner=True))

    assert rule_of(result).outcome == RuleOutcome.NOT_FIRED


@pytest.mark.parametrize("flow", [Flow.PF_PJ, Flow.PJ_PF, Flow.PJ_PJ])
def test_flows_other_than_individual_to_individual_are_outside_the_rule(make_context, local_datetime, flow):
    result = evaluate(night_context(make_context, local_datetime, 150000, flow=flow))

    assert rule_of(result).outcome == RuleOutcome.NOT_FIRED
    assert result.how.level == RiskLevel.OK


def test_challenge_payload_shape_gives_how_suspicious_and_two_factor(make_context, local_datetime):
    result = evaluate(night_context(make_context, local_datetime, 150000))

    assert result.how.level == RiskLevel.SUSPICIOUS
    assert result.decision == Decision.TWO_FACTOR_REQUIRED
