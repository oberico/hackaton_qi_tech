import dataclasses

from src.engine import floors, maturity, matrix, policy, trust
from src.engine.analyzers import how, where, who
from src.engine.risk_context import Decision, DecisionBasis, EngineResult, RiskContext, RuleOutcome
from src.engine.rules import axis_result


def evaluate(context: RiskContext) -> EngineResult:
    who_rules = who.analyze(context)
    how_rules = how.analyze(context)
    where_rules = where.analyze(context)
    axes = {"who": axis_result(who_rules), "how": axis_result(how_rules), "where": axis_result(where_rules)}
    levels = {name: axis.level for name, axis in axes.items()}
    raw_decision, _ = matrix.decide(levels["who"], levels["how"], levels["where"])

    trusted_levels, applied_signals = trust.downgrade(levels, trust.detect_signals(context))
    decision, basis = matrix.decide(trusted_levels["who"], trusted_levels["how"], trusted_levels["where"])
    if applied_signals and decision != raw_decision:
        basis = DecisionBasis.TRUST_DOWNGRADE

    floor_rules = floors.evaluate_floors(context)
    fired_floors = [rule.code for rule in floor_rules if rule.outcome == RuleOutcome.FIRED]
    if fired_floors and decision == Decision.APPROVED:
        decision, basis = Decision.TWO_FACTOR_REQUIRED, DecisionBasis.REGULATORY_FLOOR

    return EngineResult(
        decision=decision,
        decision_basis=basis,
        who=dataclasses.replace(axes["who"], level=trusted_levels["who"]),
        how=dataclasses.replace(axes["how"], level=trusted_levels["how"]),
        where=dataclasses.replace(axes["where"], level=trusted_levels["where"]),
        floors=fired_floors,
        trust_signals=applied_signals,
        maturity_phase=maturity.payer_phase(context.payer.approved_count, context.payer.relationship_days),
        policy_version=policy.POLICY_VERSION,
        evaluated_rules=who_rules + how_rules + where_rules + floor_rules + trust.evaluate_signals(context),
    )
