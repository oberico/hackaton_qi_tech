import pytest

from src.engine import trust
from src.engine.analyzers import where
from src.engine.engine import evaluate
from src.engine.risk_context import Decision, DecisionBasis, DeviceTrust, RiskLevel
from src.engine.rules import fired

OK = RiskLevel.OK
SUSPICIOUS = RiskLevel.SUSPICIOUS
CRITICAL = RiskLevel.CRITICAL
SIGNAL = "TRUST_RECURRENT_BENEFICIARY"


def levels(who=OK, how=OK, where=OK):
    return {"who": who, "how": how, "where": where}


def test_signal_downgrades_a_single_suspicious_axis_to_ok():
    result, applied = trust.downgrade(levels(how=SUSPICIOUS), [SIGNAL])

    assert result == levels()
    assert applied == [SIGNAL]


def test_signal_downgrades_only_one_of_two_suspicious_axes():
    result, applied = trust.downgrade(levels(how=SUSPICIOUS, where=SUSPICIOUS), [SIGNAL])

    assert result == levels(where=SUSPICIOUS)
    assert applied == [SIGNAL]


def test_who_is_downgraded_before_where():
    result, applied = trust.downgrade(levels(who=SUSPICIOUS, where=SUSPICIOUS), [SIGNAL])

    assert result == levels(where=SUSPICIOUS)
    assert applied == [SIGNAL]


def test_where_alone_is_downgraded():
    result, applied = trust.downgrade(levels(where=SUSPICIOUS), [SIGNAL])

    assert result == levels()
    assert applied == [SIGNAL]


@pytest.mark.parametrize("critical_axis", ["who", "how", "where"])
def test_signal_never_downgrades_a_critical_axis(critical_axis):
    original = levels(**{critical_axis: CRITICAL})

    result, applied = trust.downgrade(original, [SIGNAL])

    assert result == original
    assert applied == []


def test_critical_axis_is_kept_while_a_suspicious_one_is_still_downgraded():
    result, applied = trust.downgrade(levels(where=CRITICAL, how=SUSPICIOUS), [SIGNAL])

    assert result == levels(where=CRITICAL)
    assert applied == [SIGNAL]


def test_two_signals_still_downgrade_a_single_axis():
    result, applied = trust.downgrade(levels(how=SUSPICIOUS, where=SUSPICIOUS), [SIGNAL, "TRUST_MATURE_SELF_PIX"])

    assert result == levels(where=SUSPICIOUS)
    assert applied == [SIGNAL]


def test_no_signal_keeps_the_levels():
    original = levels(how=SUSPICIOUS)

    assert trust.downgrade(original, []) == (original, [])


def test_signal_without_suspicious_axis_is_not_applied():
    assert trust.downgrade(levels(), [SIGNAL]) == (levels(), [])


def night_pix(make_context, local_datetime, device_trust=DeviceTrust.TRUSTED):
    return make_context(
        transaction={"amount": 150000, "transaction_date": local_datetime(22, 15)},
        payer={"device_trust": device_trust},
    )


def test_downgrade_of_the_only_suspicious_axis_is_applied_but_the_night_floor_remains(make_context, local_datetime, monkeypatch):
    monkeypatch.setattr(trust, "detect_signals", lambda context: [SIGNAL])

    result = evaluate(night_pix(make_context, local_datetime))

    assert result.how.level == OK
    assert result.trust_signals == [SIGNAL]
    assert result.decision == Decision.TWO_FACTOR_REQUIRED
    assert result.decision_basis == DecisionBasis.REGULATORY_FLOOR


def test_downgrade_of_one_of_two_suspicious_axes_turns_rejection_into_two_factor(make_context, local_datetime, monkeypatch):
    stub = fired("WHERE_STUB", "where", SUSPICIOUS, {}, {}, "stub", "stub")
    monkeypatch.setattr(where, "analyze", lambda context: [stub])
    monkeypatch.setattr(trust, "detect_signals", lambda context: [SIGNAL])

    result = evaluate(night_pix(make_context, local_datetime))

    assert result.how.level == OK
    assert [reason.code for reason in result.how.rules] == ["HOW_NIGHT_LIMIT_EXCEEDED"]
    assert result.where.level == SUSPICIOUS
    assert result.decision == Decision.TWO_FACTOR_REQUIRED
    assert result.decision_basis == DecisionBasis.TRUST_DOWNGRADE
    assert result.trust_signals == [SIGNAL]


def test_downgrade_that_makes_the_pix_clean_is_a_trust_downgrade(make_context, monkeypatch):
    stub = fired("WHERE_STUB", "where", SUSPICIOUS, {}, {}, "stub", "stub")
    monkeypatch.setattr(where, "analyze", lambda context: [stub])
    monkeypatch.setattr(trust, "detect_signals", lambda context: [SIGNAL])

    result = evaluate(make_context(payer={"device_trust": DeviceTrust.TRUSTED}))

    assert result.decision == Decision.APPROVED
    assert result.decision_basis == DecisionBasis.TRUST_DOWNGRADE


def test_critical_axis_is_still_rejected_with_a_signal(make_context, monkeypatch):
    stub = fired("WHERE_STUB", "where", CRITICAL, {}, {}, "stub", "stub")
    monkeypatch.setattr(where, "analyze", lambda context: [stub])
    monkeypatch.setattr(trust, "detect_signals", lambda context: [SIGNAL])

    result = evaluate(make_context())

    assert result.decision == Decision.REJECTED
    assert result.decision_basis == DecisionBasis.CRITICAL_AXIS
    assert result.trust_signals == []


def test_without_signals_trust_signals_is_empty(make_context):
    assert evaluate(make_context()).trust_signals == []
