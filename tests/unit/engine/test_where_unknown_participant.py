from src.engine.engine import evaluate
from src.engine.risk_context import Decision, RiskLevel, RuleOutcome

CODE = "WHERE_UNKNOWN_PARTICIPANT"


def rule_of(result):
    matches = [rule for rule in result.evaluated_rules if rule.code == CODE]
    assert len(matches) == 1, f"{CODE} was not evaluated"
    return matches[0]


def participant_context(make_context, listed):
    return make_context(transaction={"destination_participant_listed": listed})


def test_unlisted_participant_makes_where_suspicious(make_context):
    result = evaluate(participant_context(make_context, listed=False))

    assert result.where.level == RiskLevel.SUSPICIOUS
    assert [reason.code for reason in result.where.rules] == [CODE]
    assert result.decision == Decision.TWO_FACTOR_REQUIRED


def test_unlisted_participant_reason_carries_observed_and_threshold(make_context):
    rule = rule_of(evaluate(participant_context(make_context, listed=False)))

    assert rule.outcome == RuleOutcome.FIRED
    assert rule.axis == "where"
    assert rule.level == RiskLevel.SUSPICIOUS
    assert rule.observed == {"destination_participant_listed": False}
    assert rule.threshold == {"destination_participant_listed": True}
    assert rule.description
    assert rule.translation


def test_listed_participant_does_not_fire(make_context):
    result = evaluate(participant_context(make_context, listed=True))

    assert rule_of(result).outcome == RuleOutcome.NOT_FIRED
    assert result.where.level == RiskLevel.OK
    assert result.decision == Decision.APPROVED
