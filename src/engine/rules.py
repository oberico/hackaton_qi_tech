from typing import Any, Dict, List, Optional

from src.engine.risk_context import AxisResult, EvaluatedRule, RiskLevel, RuleOutcome, TriggeredRule

LEVEL_ORDER = {RiskLevel.OK: 0, RiskLevel.SUSPICIOUS: 1, RiskLevel.CRITICAL: 2}


def fired(code: str, axis: str, level: RiskLevel, observed: Dict[str, Any], threshold: Dict[str, Any], description: str, translation: str) -> EvaluatedRule:
    return EvaluatedRule(code, axis, RuleOutcome.FIRED, level, observed, threshold, description, translation)


def not_fired(code: str, axis: str, description: str, translation: str, observed: Optional[Dict[str, Any]] = None, threshold: Optional[Dict[str, Any]] = None) -> EvaluatedRule:
    return EvaluatedRule(code, axis, RuleOutcome.NOT_FIRED, None, observed, threshold, description, translation)


def unavailable(code: str, axis: str, description: str, translation: str) -> EvaluatedRule:
    return EvaluatedRule(code, axis, RuleOutcome.UNAVAILABLE, None, None, None, description, translation)


def axis_result(evaluated_rules: List[EvaluatedRule]) -> AxisResult:
    triggered = [
        TriggeredRule(rule.code, rule.axis, rule.level, rule.observed, rule.threshold, rule.description, rule.translation)
        for rule in evaluated_rules
        if rule.outcome == RuleOutcome.FIRED
    ]
    level = max((rule.level for rule in triggered), key=LEVEL_ORDER.get, default=RiskLevel.OK)
    return AxisResult(level=level, rules=triggered)
