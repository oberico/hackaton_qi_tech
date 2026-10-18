from src.engine import floors, maturity, matrix, policy
from src.engine.analyzers import how, where, who
from src.engine.risk_context import Decision, DecisionBasis, EngineResult, RiskContext, RuleOutcome
from src.engine.rules import axis_result


def evaluate(context: RiskContext) -> EngineResult:
    who_rules = who.analyze(context)
    how_rules = how.analyze(context)
    where_rules = where.analyze(context)
    who_axis = axis_result(who_rules)
    how_axis = axis_result(how_rules)
    where_axis = axis_result(where_rules)
    decision, basis = matrix.decide(who_axis.level, how_axis.level, where_axis.level)
    floor_rules = floors.evaluate_floors(context)
    fired_floors = [rule.code for rule in floor_rules if rule.outcome == RuleOutcome.FIRED]
    if fired_floors and decision == Decision.APPROVED:
        decision, basis = Decision.TWO_FACTOR_REQUIRED, DecisionBasis.REGULATORY_FLOOR
    return EngineResult(
        decision=decision,
        decision_basis=basis,
        who=who_axis,
        how=how_axis,
        where=where_axis,
        floors=fired_floors,
        trust_signals=[],
        maturity_phase=maturity.payer_phase(context.payer.approved_count, context.payer.relationship_days),
        policy_version=policy.POLICY_VERSION,
        evaluated_rules=who_rules + how_rules + where_rules + floor_rules,
    )
