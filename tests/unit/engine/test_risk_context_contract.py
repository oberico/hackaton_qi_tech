import dataclasses

import pytest

from src.engine.risk_context import (
    AxisResult,
    Decision,
    DecisionBasis,
    EngineResult,
    EvaluatedRule,
    RiskLevel,
    RuleOutcome,
    TriggeredRule,
)


def build_triggered_rule():
    return TriggeredRule(
        code="HOW_NIGHT_LIMIT_EXCEEDED",
        axis="how",
        level=RiskLevel.SUSPICIOUS,
        observed={"night_amount": 150000},
        threshold={"night_amount": 100000},
        description="Night-time amount above R$ 1,000.",
        translation="Soma noturna acima de R$ 1.000.",
    )


def build_not_fired_rule():
    return EvaluatedRule(
        code="WHO_DEVICE_UNKNOWN",
        axis="who",
        outcome=RuleOutcome.NOT_FIRED,
        level=None,
        observed=None,
        threshold=None,
        description="Device unknown for a payer with history.",
        translation="Device desconhecido para pagador com histórico.",
    )


def test_rule_outcome_values():
    assert RuleOutcome.FIRED.value == "fired"
    assert RuleOutcome.NOT_FIRED.value == "not_fired"
    assert RuleOutcome.UNAVAILABLE.value == "unavailable"


def test_triggered_rule_carries_dicts_and_texts():
    rule = build_triggered_rule()
    assert rule.observed == {"night_amount": 150000}
    assert rule.threshold == {"night_amount": 100000}
    assert rule.description.startswith("Night-time")
    assert rule.translation.startswith("Soma")


def test_evaluated_rule_not_fired_has_no_level_or_values():
    rule = build_not_fired_rule()
    assert rule.outcome is RuleOutcome.NOT_FIRED
    assert rule.level is None
    assert rule.observed is None
    assert rule.threshold is None


def test_engine_result_holds_evaluated_rules():
    evaluated = [build_not_fired_rule()]
    result = EngineResult(
        decision=Decision.APPROVED,
        decision_basis=DecisionBasis.CLEAN,
        who=AxisResult(level=RiskLevel.OK),
        how=AxisResult(level=RiskLevel.OK),
        where=AxisResult(level=RiskLevel.OK),
        floors=[],
        trust_signals=[],
        maturity_phase=0,
        policy_version="test",
        evaluated_rules=evaluated,
    )
    assert result.evaluated_rules == evaluated


def test_contract_dataclasses_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        build_triggered_rule().code = "OTHER"
    with pytest.raises(dataclasses.FrozenInstanceError):
        build_not_fired_rule().outcome = RuleOutcome.FIRED
