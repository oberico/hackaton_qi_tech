from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PersonaRunResult:
    code: str
    name: str
    kind: str
    total: int = 0
    approved: int = 0
    two_factor: int = 0
    rejected: int = 0
    reasons: Dict[str, int] = field(default_factory=dict)
    budget_passed: bool = False
    budget_notes: str = ""


@dataclass
class FarmReport:
    policy_version: str
    total_transactions: int
    total_approved: int
    total_two_factor: int
    total_rejected: int
    personas: List[PersonaRunResult]
    all_budgets_passed: bool


def evaluate_persona_results(code: str, name: str, kind: str, responses: List[dict]) -> PersonaRunResult:
    raise NotImplementedError


def build_farm_report(policy_version: str, personas_results: List[PersonaRunResult]) -> FarmReport:
    raise NotImplementedError


def format_farm_report_table(report: FarmReport) -> str:
    raise NotImplementedError


def run_farm(base_url: str = "http://localhost:8001", token: str = "internal-token-dev", seed: Optional[str] = None, personas: Optional[list] = None) -> FarmReport:
    raise NotImplementedError
