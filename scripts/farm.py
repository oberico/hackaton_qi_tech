import argparse
from collections import Counter
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional
import urllib.error
import urllib.request
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.utils.personas import ALL_PERSONAS, Persona  # noqa: E402


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


def evaluate_persona_results(
    code: str,
    name: str,
    kind: str,
    responses: List[dict],
) -> PersonaRunResult:
    total = len(responses)
    approved = sum(1 for r in responses if r.get("status") == "approved")
    two_factor = sum(1 for r in responses if r.get("status") == "two_factor_required")
    rejected = sum(1 for r in responses if r.get("status") == "rejected")

    reasons: Counter = Counter()
    for r in responses:
        metadata = r.get("metadata") or {}
        for reason in metadata.get("reasons") or []:
            rule_code = reason.get("code")
            if rule_code:
                reasons[rule_code] += 1

    budget_passed = True
    budget_notes = "OK"

    if kind == "legitimate":
        two_factor_pct = (two_factor / total) if total > 0 else 0.0
        if rejected > 0:
            budget_passed = False
            budget_notes = f"FALHA: {rejected} rejeição indevida (meta: 0)"
        elif two_factor_pct > 0.10:
            budget_passed = False
            budget_notes = f"FALHA: 2FA acima do limite de 10% ({two_factor_pct * 100:.1f}%)"
        else:
            budget_notes = "PASS (0 rejeições, 2FA <= 10%)"
    else:
        if rejected > 0:
            budget_notes = f"PASS ({rejected} rejeições mitigadas)"
        elif two_factor > 0:
            budget_notes = f"PASS ({two_factor} retidos em 2FA)"
        else:
            budget_passed = False
            budget_notes = "ALERTA: nenhuma transação retida"

    return PersonaRunResult(
        code=code,
        name=name,
        kind=kind,
        total=total,
        approved=approved,
        two_factor=two_factor,
        rejected=rejected,
        reasons=dict(reasons),
        budget_passed=budget_passed,
        budget_notes=budget_notes,
    )


def build_farm_report(
    policy_version: str,
    personas_results: List[PersonaRunResult],
) -> FarmReport:
    total_tx = sum(p.total for p in personas_results)
    total_app = sum(p.approved for p in personas_results)
    total_2fa = sum(p.two_factor for p in personas_results)
    total_rej = sum(p.rejected for p in personas_results)

    all_budgets_passed = all(
        p.budget_passed for p in personas_results if p.kind == "legitimate"
    )

    return FarmReport(
        policy_version=policy_version,
        total_transactions=total_tx,
        total_approved=total_app,
        total_two_factor=total_2fa,
        total_rejected=total_rej,
        personas=personas_results,
        all_budgets_passed=all_budgets_passed,
    )


def format_farm_report_table(report: FarmReport) -> str:
    lines = []
    lines.append("=" * 105)
    lines.append("  SIMULADOR DE PERSONAS E DESEMPENHO ANTIFRAUDE (FARM)")
    lines.append("=" * 105)
    lines.append(f"Policy Version:             {report.policy_version}")
    lines.append(f"Transações Simuladas:       {report.total_transactions}")

    app_pct = (report.total_approved / report.total_transactions * 100) if report.total_transactions else 0.0
    two_pct = (report.total_two_factor / report.total_transactions * 100) if report.total_transactions else 0.0
    rej_pct = (report.total_rejected / report.total_transactions * 100) if report.total_transactions else 0.0

    lines.append(
        f"Distribuição Geral:         "
        f"Aprovadas: {report.total_approved} ({app_pct:.1f}%) | "
        f"2FA: {report.total_two_factor} ({two_pct:.1f}%) | "
        f"Rejeitadas: {report.total_rejected} ({rej_pct:.1f}%)"
    )
    budget_status = (
        "ATENDIDO (0% falsos positivos em legítimas)"
        if report.all_budgets_passed
        else "NÃO ATENDIDO"
    )
    lines.append(f"Orçamento Regulatório:      {budget_status}")
    lines.append("-" * 105)
    header = (
        f"{'Persona':<36} {'Tipo':<12} {'Total':<7} "
        f"{'Approved':<10} {'2FA':<8} {'Rejected':<10} {'Orçamento':<20}"
    )
    lines.append(header)
    lines.append("-" * 105)

    all_reasons: Counter = Counter()
    for p in report.personas:
        app_s = f"{p.approved} ({(p.approved / p.total * 100 if p.total else 0.0):.0f}%)"
        two_s = f"{p.two_factor} ({(p.two_factor / p.total * 100 if p.total else 0.0):.0f}%)"
        rej_s = f"{p.rejected} ({(p.rejected / p.total * 100 if p.total else 0.0):.0f}%)"
        tipo = "Legítima" if p.kind == "legitimate" else "Fraude"
        line = (
            f"{p.name:<36} {tipo:<12} {p.total:<7} "
            f"{app_s:<10} {two_s:<8} {rej_s:<10} {p.budget_notes:<20}"
        )
        lines.append(line)
        for r_code, count in p.reasons.items():
            all_reasons[r_code] += count

    lines.append("-" * 105)
    tot_app = f"{report.total_approved} ({app_pct:.0f}%)"
    tot_two = f"{report.total_two_factor} ({two_pct:.0f}%)"
    tot_rej = f"{report.total_rejected} ({rej_pct:.0f}%)"
    summary_line = (
        f"{'TOTAL':<36} {'':<12} {report.total_transactions:<7} "
        f"{tot_app:<10} {tot_two:<8} {tot_rej:<10} "
        f"{'[PASS]' if report.all_budgets_passed else '[FAIL]':<20}"
    )
    lines.append(summary_line)
    lines.append("=" * 105)

    if all_reasons:
        lines.append("Regras Disparadas no Cenário:")
        for rule, count in all_reasons.most_common():
            lines.append(f"  * {rule:<32} {count:>3} disparo(s)")
        lines.append("=" * 105)

    return "\n".join(lines)


MAX_PERSONA_ATTEMPTS = 5


def post_pix(url: str, token: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "INTERNAL-TOKEN": token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"status": "error", "error": str(e)}


def run_farm(
    base_url: str = "http://localhost:8001",
    token: str = "internal-token-dev",
    seed: Optional[str] = None,
    personas: Optional[List[Persona]] = None,
) -> FarmReport:
    active_seed = seed or f"farm-{uuid.uuid4().hex[:6]}"
    active_personas = personas or ALL_PERSONAS
    url = f"{base_url.rstrip('/')}/pix/transaction"

    policy_version = "2026.10.18-1"
    personas_results: List[PersonaRunResult] = []

    for persona in active_personas:
        for attempt in range(MAX_PERSONA_ATTEMPTS):
            persona_seed = active_seed if attempt == 0 else f"{active_seed}-retry{attempt}"
            responses = []
            for payload in persona.generator(persona_seed):
                response = post_pix(url, token, payload)
                responses.append(response)
                pv = response.get("metadata", {}).get("policy_version")
                if pv:
                    policy_version = pv
            if all("metadata" in response for response in responses):
                break

        res = evaluate_persona_results(
            code=persona.code,
            name=persona.name,
            kind=persona.kind,
            responses=responses,
        )
        personas_results.append(res)

    return build_farm_report(policy_version, personas_results)


def main():
    parser = argparse.ArgumentParser(
        description="Simulador de Personas e Desempenho Antifraude Pix (Farm)"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8001",
        help="URL base da API (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--token",
        default="internal-token-dev",
        help="Token de autenticacao de servico (default: internal-token-dev)",
    )
    parser.add_argument(
        "--seed",
        default=None,
        help="Semente opcional para geracao deterministica de payloads",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Numero de repeticoes da simulacao (default: 1)",
    )

    args = parser.parse_args()

    for run_idx in range(args.runs):
        run_seed = args.seed or f"run-{run_idx}-{uuid.uuid4().hex[:6]}"
        start_time = time.time()
        report = run_farm(
            base_url=args.base_url,
            token=args.token,
            seed=run_seed,
        )
        elapsed = time.time() - start_time
        print(format_farm_report_table(report))
        print(f"Executado em {elapsed:.2f} s | Seed: {run_seed}\n")


if __name__ == "__main__":
    main()
