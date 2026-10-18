from src.engine import policy


def payer_phase(approved_count: int, relationship_days: float) -> int:
    if approved_count == 0:
        return 0
    mature = approved_count >= policy.MATURE_PAYER_MIN_APPROVED and relationship_days >= policy.MATURE_PAYER_MIN_RELATIONSHIP_DAYS
    return 2 if mature else 1
