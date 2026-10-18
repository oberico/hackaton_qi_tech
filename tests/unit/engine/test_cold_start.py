from src.engine.analyzers import where
from src.engine.engine import evaluate
from src.engine.risk_context import Decision, DecisionBasis, DeviceTrust, RiskLevel, RuleOutcome
from src.engine.rules import fired

HOW_NIGHT_LIMIT = "HOW_NIGHT_LIMIT_EXCEEDED"


def destination_new_account_stub():
    return fired("WHERE_STUB", "where", RiskLevel.SUSPICIOUS, {"destination_account_age_days": 7}, {"days": 30}, "stub", "stub")


def challenge_payload_context(make_context, local_datetime, destination_account_age_days=400):
    return make_context(
        transaction={
            "amount": 150000,
            "transaction_date": local_datetime(22, 15),
            "destination_account_age_days": destination_account_age_days,
        },
    )


def test_payer_without_any_history_is_approved_and_clean(make_context):
    result = evaluate(make_context())

    assert result.decision == Decision.APPROVED
    assert result.decision_basis == DecisionBasis.CLEAN
    assert result.maturity_phase == 0
    assert (result.who.level, result.how.level, result.where.level) == (RiskLevel.OK, RiskLevel.OK, RiskLevel.OK)
    assert result.floors == []
    assert result.trust_signals == []


def test_absence_of_history_fires_no_rule(make_context):
    result = evaluate(make_context())

    assert all(rule.outcome != RuleOutcome.FIRED for rule in result.evaluated_rules)


def test_first_pix_with_a_single_payload_signal_is_never_rejected(make_context, local_datetime):
    result = evaluate(challenge_payload_context(make_context, local_datetime))

    assert result.decision == Decision.TWO_FACTOR_REQUIRED
    assert result.decision_basis == DecisionBasis.SINGLE_SUSPICIOUS_AXIS


def test_first_pix_with_payload_evidence_in_two_axes_is_rejected(make_context, local_datetime, monkeypatch):
    monkeypatch.setattr(where, "analyze", lambda context: [destination_new_account_stub()])

    result = evaluate(challenge_payload_context(make_context, local_datetime, destination_account_age_days=7))

    assert result.decision == Decision.REJECTED
    assert result.decision_basis == DecisionBasis.TWO_SUSPICIOUS_AXES
    assert result.maturity_phase == 0
    assert HOW_NIGHT_LIMIT in [reason.code for reason in result.how.rules]
    assert [reason.code for reason in result.where.rules] == ["WHERE_STUB"]


def test_reasons_carry_observed_threshold_and_both_languages(make_context, local_datetime):
    result = evaluate(challenge_payload_context(make_context, local_datetime))

    reason = result.how.rules[0]
    assert reason.observed == {"night_amount": 150000}
    assert reason.threshold == {"night_amount": 100000}
    assert reason.description and reason.translation


def test_every_evaluated_rule_is_listed_once(make_context):
    result = evaluate(make_context())

    codes = [rule.code for rule in result.evaluated_rules]
    assert len(codes) == len(set(codes))
    assert {HOW_NIGHT_LIMIT, "FLOOR_UNREGISTERED_DEVICE", "FLOOR_NIGHT_LIMIT"} <= set(codes)


def test_policy_version_is_reported(make_context):
    assert evaluate(make_context()).policy_version == "2026.10.18-1"


def test_established_payer_reports_phase_two(make_context):
    result = evaluate(make_context(payer={"approved_count": 8, "relationship_days": 120, "device_trust": DeviceTrust.TRUSTED}))

    assert result.maturity_phase == 2
