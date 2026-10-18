import pytest

from src.engine.analyzers import where
from src.engine.engine import evaluate
from src.engine.risk_context import Decision, DecisionBasis, DeviceTrust, Flow, RiskLevel, RuleOutcome
from src.engine.rules import fired

UNREGISTERED_DEVICE = "FLOOR_UNREGISTERED_DEVICE"
NIGHT_LIMIT = "FLOOR_NIGHT_LIMIT"


def rule_of(result, code):
    return next(rule for rule in result.evaluated_rules if rule.code == code)


def test_unregistered_device_above_two_hundred_reais_requires_two_factor(make_context):
    result = evaluate(make_context(transaction={"amount": 20001}))

    assert result.floors == [UNREGISTERED_DEVICE]
    assert result.decision == Decision.TWO_FACTOR_REQUIRED
    assert result.decision_basis == DecisionBasis.REGULATORY_FLOOR
    rule = rule_of(result, UNREGISTERED_DEVICE)
    assert rule.axis == "floor"
    assert rule.outcome == RuleOutcome.FIRED
    assert rule.observed["amount"] == 20001
    assert rule.threshold["amount"] == 20000


def test_unregistered_device_at_exactly_two_hundred_reais_is_approved(make_context):
    result = evaluate(make_context(transaction={"amount": 20000}))

    assert result.floors == []
    assert result.decision == Decision.APPROVED
    assert rule_of(result, UNREGISTERED_DEVICE).outcome == RuleOutcome.NOT_FIRED


@pytest.mark.parametrize("trust", [DeviceTrust.OBSERVING, DeviceTrust.TRUSTED])
def test_known_device_has_no_unregistered_device_floor(make_context, trust):
    result = evaluate(make_context(transaction={"amount": 50000}, payer={"device_trust": trust}))

    assert result.floors == []
    assert result.decision == Decision.APPROVED


def test_company_payer_has_no_unregistered_device_floor(make_context):
    result = evaluate(make_context(transaction={"amount": 50000, "flow": Flow.PJ_PF}))

    assert result.floors == []
    assert result.decision == Decision.APPROVED


def test_unregistered_device_daily_sum_above_one_thousand_reais_triggers_the_floor(make_context):
    result = evaluate(make_context(transaction={"amount": 10000}, payer={"unknown_device_amount_today": 95000}))

    assert result.floors == [UNREGISTERED_DEVICE]
    assert rule_of(result, UNREGISTERED_DEVICE).observed["daily_amount"] == 105000


def test_unregistered_device_daily_sum_at_exactly_one_thousand_reais_does_not_trigger(make_context):
    result = evaluate(make_context(transaction={"amount": 10000}, payer={"unknown_device_amount_today": 90000}))

    assert result.floors == []


def test_night_floor_for_individual_to_individual_above_one_thousand_reais(make_context, local_datetime):
    result = evaluate(
        make_context(
            transaction={"amount": 60000, "transaction_date": local_datetime(22, 15)},
            payer={"device_trust": DeviceTrust.TRUSTED, "night_amount_to_individuals": 50000},
        )
    )

    assert result.floors == [NIGHT_LIMIT]
    assert rule_of(result, NIGHT_LIMIT).observed == {"night_amount": 110000}
    assert rule_of(result, NIGHT_LIMIT).threshold == {"night_amount": 100000}
    assert result.decision == Decision.TWO_FACTOR_REQUIRED


def test_night_floor_at_exactly_one_thousand_reais_does_not_trigger(make_context, local_datetime):
    result = evaluate(
        make_context(
            transaction={"amount": 100000, "transaction_date": local_datetime(22, 15)},
            payer={"device_trust": DeviceTrust.TRUSTED},
        )
    )

    assert result.floors == []
    assert result.decision == Decision.APPROVED


@pytest.mark.parametrize("overrides", [{"same_owner": True}, {"flow": Flow.PF_PJ}, {"flow": Flow.PJ_PF}])
def test_night_floor_does_not_apply_to_self_pix_or_other_flows(make_context, local_datetime, overrides):
    result = evaluate(
        make_context(
            transaction={"amount": 150000, "transaction_date": local_datetime(22, 15), **overrides},
            payer={"device_trust": DeviceTrust.TRUSTED},
        )
    )

    assert NIGHT_LIMIT not in result.floors


def test_floor_never_softens_a_rejection(make_context, monkeypatch, local_datetime):
    suspicious = fired("WHERE_STUB", "where", RiskLevel.SUSPICIOUS, {}, {}, "stub", "stub")
    monkeypatch.setattr(where, "analyze", lambda context: [suspicious])

    result = evaluate(make_context(transaction={"amount": 150000, "transaction_date": local_datetime(22, 15)}))

    assert result.decision == Decision.REJECTED
    assert result.decision_basis == DecisionBasis.TWO_SUSPICIOUS_AXES
    assert NIGHT_LIMIT in result.floors


def test_unregistered_device_floor_alone_never_rejects(make_context):
    result = evaluate(make_context(transaction={"amount": 5000000}, payer={"unknown_device_amount_today": 5000000}))

    assert result.floors == [UNREGISTERED_DEVICE]
    assert result.decision == Decision.TWO_FACTOR_REQUIRED


def test_rejection_from_another_axis_prevails_over_the_unregistered_device_floor(make_context, monkeypatch):
    critical = fired("WHERE_STUB", "where", RiskLevel.CRITICAL, {}, {}, "stub", "stub")
    monkeypatch.setattr(where, "analyze", lambda context: [critical])

    result = evaluate(make_context(transaction={"amount": 50000}))

    assert result.decision == Decision.REJECTED
    assert result.decision_basis == DecisionBasis.CRITICAL_AXIS
    assert result.floors == [UNREGISTERED_DEVICE]
