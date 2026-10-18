from src.engine import policy
from src.engine.engine import evaluate
from src.engine.risk_context import Decision, RiskLevel, RuleOutcome

CODE = "WHERE_DESTINATION_NEW_ACCOUNT"


def rule_of(result):
    matches = [rule for rule in result.evaluated_rules if rule.code == CODE]
    assert len(matches) == 1, f"{CODE} was not evaluated"
    return matches[0]


def destination_context(make_context, age_days):
    return make_context(transaction={"destination_account_age_days": age_days})


def test_seven_day_old_destination_makes_where_suspicious(make_context):
    result = evaluate(destination_context(make_context, 7))

    assert result.where.level == RiskLevel.SUSPICIOUS
    assert [reason.code for reason in result.where.rules] == [CODE]
    assert result.decision == Decision.TWO_FACTOR_REQUIRED


def test_reason_carries_observed_and_threshold(make_context):
    rule = rule_of(evaluate(destination_context(make_context, 7)))

    assert rule.outcome == RuleOutcome.FIRED
    assert rule.axis == "where"
    assert rule.level == RiskLevel.SUSPICIOUS
    assert rule.observed == {"destination_account_age_days": 7}
    assert rule.threshold == {"destination_account_age_days": policy.DESTINATION_NEW_ACCOUNT_DAYS}
    assert rule.description
    assert rule.translation
