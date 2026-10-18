from src.engine.engine import evaluate
from src.engine.risk_context import Decision, DecisionBasis, RiskLevel


def night_pf_pf_context(make_context, local_datetime, **transaction):
    return make_context(
        transaction={"amount": 150000, "transaction_date": local_datetime(22, 15), **transaction},
    )


def test_new_destination_with_night_limit_is_rejected_by_two_suspicious_axes(make_context, local_datetime):
    result = evaluate(night_pf_pf_context(make_context, local_datetime, destination_account_age_days=7))

    assert result.how.level == RiskLevel.SUSPICIOUS
    assert result.where.level == RiskLevel.SUSPICIOUS
    assert result.decision == Decision.REJECTED
    assert result.decision_basis == DecisionBasis.TWO_SUSPICIOUS_AXES


def test_new_destination_alone_requires_two_factor(make_context):
    result = evaluate(make_context(transaction={"destination_account_age_days": 7}))

    assert result.where.level == RiskLevel.SUSPICIOUS
    assert result.decision == Decision.TWO_FACTOR_REQUIRED
    assert result.decision_basis == DecisionBasis.SINGLE_SUSPICIOUS_AXIS


def test_unlisted_participant_with_night_limit_is_rejected_by_two_suspicious_axes(make_context, local_datetime):
    result = evaluate(night_pf_pf_context(make_context, local_datetime, destination_participant_listed=False))

    assert result.decision == Decision.REJECTED
    assert result.decision_basis == DecisionBasis.TWO_SUSPICIOUS_AXES


def test_both_where_rules_together_stay_in_one_suspicious_axis(make_context):
    result = evaluate(make_context(transaction={"destination_account_age_days": 7, "destination_participant_listed": False}))

    assert result.where.level == RiskLevel.SUSPICIOUS
    assert len(result.where.rules) == 2
    assert result.decision == Decision.TWO_FACTOR_REQUIRED
    assert result.decision_basis == DecisionBasis.SINGLE_SUSPICIOUS_AXIS
