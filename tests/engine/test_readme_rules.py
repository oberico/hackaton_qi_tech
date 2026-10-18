import re
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.engine import policy as real_policy
from src.engine.engine import evaluate
from src.engine.risk_context import Flow
from tests.engine.conftest import make_context

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_HEADING = "## Regras"
PARAMETER_PATTERN = re.compile(r"^`(?P<name>[A-Z0-9_]+)(?:\[(?P<flow>[a-z_]+)\])?(?:\.(?P<key>[a-z_]+))?`\s*=\s*(?P<value>.+)$")
VALUE_PATTERN = re.compile(r"^(?:R\$\s*)?(?P<number>[\d.]+(?:,\d+)?)\s*(?P<unit>h|dias|dia)?$")
MINOR_SUFFIX = "_MINOR"
CENTS_PER_REAL = 100


def rules_table_rows(readme_text):
    in_section = False
    rows = []
    for line in readme_text.splitlines():
        if line.startswith("## "):
            in_section = line.strip() == RULES_HEADING
            continue
        if in_section and line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            code = re.fullmatch(r"`([A-Z][A-Z0-9_]+)`", cells[0])
            if code and len(cells) >= 3:
                rows.append((code.group(1), cells[2]))
    return rows


def parse_value(raw):
    match = VALUE_PATTERN.match(raw.strip())
    if not match:
        raise ValueError(f"unparseable value {raw!r}")
    return Decimal(match.group("number").replace(".", "").replace(",", "."))


def parse_parameters(cell):
    parameters = []
    for entry in cell.split("<br>"):
        match = PARAMETER_PATTERN.match(entry.strip())
        if match:
            parameters.append((match.group("name"), match.group("flow"), match.group("key"), match.group("value")))
    return parameters


def parse_readme_rules(readme_text):
    rules = {}
    for code, cell in rules_table_rows(readme_text):
        assert code not in rules, f"{code} has more than one row in the README rules table"
        rules[code] = parse_parameters(cell)
    return rules


def policy_value(policy, name, flow, key):
    if not hasattr(policy, name):
        return None, f"{name} does not exist in policy.py"
    value = getattr(policy, name)
    if flow is not None:
        by_flow = {getattr(k, "value", k): v for k, v in value.items()}
        if flow not in by_flow:
            return None, f"{name} has no entry for flow {flow} in policy.py"
        value = by_flow[flow]
    if key is not None:
        if value is None or key not in value:
            return None, f"{name}[{flow}] has no key {key} in policy.py"
        value = value[key]
    return value, None


def expected_policy_value(name, readme_value):
    return readme_value * CENTS_PER_REAL if name.endswith(MINOR_SUFFIX) else readme_value


def declared_rule_codes(policy):
    return {code for codes in policy.RULE_CODES.values() for code in codes}


def implemented_rule_codes():
    return {rule.code for rule in evaluate(make_context()).evaluated_rules}


def readme_policy_divergences(readme_text, policy, implemented):
    declared = declared_rule_codes(policy)
    rules = parse_readme_rules(readme_text)
    problems = []
    for code in sorted(implemented - set(rules)):
        problems.append(f"{code} is implemented in the engine but has no row in the README rules table")
    for code in sorted(set(rules) - declared):
        problems.append(f"{code} has a README row but is not declared in policy.RULE_CODES")
    for code in sorted((set(rules) - implemented) & declared):
        problems.append(f"{code} has a README row but is not implemented in the engine")
    for code, parameters in rules.items():
        for name, flow, key, raw in parameters:
            label = f"{name}" + (f"[{flow}]" if flow else "") + (f".{key}" if key else "")
            actual, missing = policy_value(policy, name, flow, key)
            if missing:
                problems.append(f"{code}: {label}: {missing}")
                continue
            try:
                documented = expected_policy_value(name, parse_value(raw))
            except ValueError as error:
                problems.append(f"{code}: {label}: {error}")
                continue
            if actual is None or Decimal(str(actual)) != documented:
                problems.append(f"{code}: {label} is {raw} in the README ({documented}) but {actual} in policy.py")
    return problems


def synthetic_policy(**overrides):
    values = {
        "RULE_CODES": {"how": ("HOW_A", "HOW_B"), "where": ("WHERE_A",)},
        "NIGHT_START_HOUR": 20,
        "LIMIT_MINOR": {Flow.PF_PF: 100000, Flow.PF_PJ: None},
        "VELOCITY": {Flow.PF_PF: {"suspicious": 3, "critical": 6}},
        "WINDOW_DAYS": 30,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def synthetic_readme(rows=None):
    default_rows = [
        ("HOW_A", "`NIGHT_START_HOUR` = 20h<br>`LIMIT_MINOR[pf_pf]` = R$ 1.000<br>`VELOCITY[pf_pf].suspicious` = 3"),
        ("WHERE_A", "`WINDOW_DAYS` = 30 dias"),
    ]
    lines = [
        "# Group",
        "## Regras",
        "| Regra | Lógica | Parâmetros | Por quê |",
        "|---|---|---|---|",
    ]
    for code, parameters in default_rows if rows is None else rows:
        lines.append(f"| `{code}` | logic | {parameters} | why |")
    lines += ["## Como as regras viram decisão", "| `NOT_A_RULE` | x | `WINDOW_DAYS` = 1 | y |"]
    return "\n".join(lines)


SYNTHETIC_IMPLEMENTED = {"HOW_A", "WHERE_A"}


class TestSyntheticReadme:
    def test_matching_readme_and_policy_have_no_divergence(self):
        assert readme_policy_divergences(synthetic_readme(), synthetic_policy(), SYNTHETIC_IMPLEMENTED) == []

    def test_implemented_rule_without_row_is_reported_by_code(self):
        readme = synthetic_readme([("HOW_A", "`NIGHT_START_HOUR` = 20h")])
        problems = readme_policy_divergences(readme, synthetic_policy(), SYNTHETIC_IMPLEMENTED)
        assert problems == ["WHERE_A is implemented in the engine but has no row in the README rules table"]

    def test_declared_but_not_implemented_rule_needs_no_row(self):
        problems = readme_policy_divergences(synthetic_readme(), synthetic_policy(), SYNTHETIC_IMPLEMENTED)
        assert not any("HOW_B" in problem for problem in problems)

    def test_row_without_declared_rule_is_reported_by_code(self):
        readme = synthetic_readme([("HOW_A", "`NIGHT_START_HOUR` = 20h"), ("WHERE_A", "`WINDOW_DAYS` = 30 dias"), ("GHOST_RULE", "x")])
        problems = readme_policy_divergences(readme, synthetic_policy(), SYNTHETIC_IMPLEMENTED)
        assert problems == ["GHOST_RULE has a README row but is not declared in policy.RULE_CODES"]

    def test_row_for_declared_but_unimplemented_rule_is_reported(self):
        readme = synthetic_readme([("HOW_A", "x"), ("WHERE_A", "x"), ("HOW_B", "x")])
        problems = readme_policy_divergences(readme, synthetic_policy(), SYNTHETIC_IMPLEMENTED)
        assert problems == ["HOW_B has a README row but is not implemented in the engine"]

    @pytest.mark.parametrize(
        "policy_override, expected",
        [
            ({"NIGHT_START_HOUR": 21}, "HOW_A: NIGHT_START_HOUR is 20h in the README (20) but 21 in policy.py"),
            ({"LIMIT_MINOR": {Flow.PF_PF: 100001}}, "HOW_A: LIMIT_MINOR[pf_pf] is R$ 1.000 in the README (100000) but 100001 in policy.py"),
            (
                {"VELOCITY": {Flow.PF_PF: {"suspicious": 4}}},
                "HOW_A: VELOCITY[pf_pf].suspicious is 3 in the README (3) but 4 in policy.py",
            ),
            ({"WINDOW_DAYS": 29}, "WHERE_A: WINDOW_DAYS is 30 dias in the README (30) but 29 in policy.py"),
        ],
        ids=["hour", "money_in_cents", "nested_dict", "days"],
    )
    def test_divergent_value_names_rule_and_constant(self, policy_override, expected):
        problems = readme_policy_divergences(synthetic_readme(), synthetic_policy(**policy_override), SYNTHETIC_IMPLEMENTED)
        assert problems == [expected]

    def test_constant_missing_from_policy_is_reported(self):
        readme = synthetic_readme([("HOW_A", "`MISSING_CONSTANT` = 3"), ("WHERE_A", "x")])
        problems = readme_policy_divergences(readme, synthetic_policy(), SYNTHETIC_IMPLEMENTED)
        assert problems == ["HOW_A: MISSING_CONSTANT: MISSING_CONSTANT does not exist in policy.py"]

    def test_flow_missing_from_policy_is_reported(self):
        readme = synthetic_readme([("HOW_A", "`LIMIT_MINOR[pj_pj]` = R$ 1"), ("WHERE_A", "x")])
        problems = readme_policy_divergences(readme, synthetic_policy(), SYNTHETIC_IMPLEMENTED)
        assert problems == ["HOW_A: LIMIT_MINOR[pj_pj]: LIMIT_MINOR has no entry for flow pj_pj in policy.py"]

    def test_flow_documented_as_value_but_none_in_policy_is_reported(self):
        readme = synthetic_readme([("HOW_A", "`LIMIT_MINOR[pf_pj]` = R$ 1.000"), ("WHERE_A", "x")])
        problems = readme_policy_divergences(readme, synthetic_policy(), SYNTHETIC_IMPLEMENTED)
        assert problems == ["HOW_A: LIMIT_MINOR[pf_pj] is R$ 1.000 in the README (100000) but None in policy.py"]

    def test_unparseable_value_is_reported(self):
        readme = synthetic_readme([("HOW_A", "`NIGHT_START_HOUR` = vinte"), ("WHERE_A", "x")])
        problems = readme_policy_divergences(readme, synthetic_policy(), SYNTHETIC_IMPLEMENTED)
        assert problems == ["HOW_A: NIGHT_START_HOUR: unparseable value 'vinte'"]

    def test_reais_with_decimal_comma_convert_to_exact_cents(self):
        readme = synthetic_readme([("HOW_A", "`LIMIT_MINOR[pf_pf]` = R$ 1.000,50"), ("WHERE_A", "x")])
        problems = readme_policy_divergences(readme, synthetic_policy(LIMIT_MINOR={Flow.PF_PF: 100050}), SYNTHETIC_IMPLEMENTED)
        assert problems == []

    def test_rows_outside_the_rules_section_are_ignored(self):
        assert "NOT_A_RULE" not in parse_readme_rules(synthetic_readme())

    def test_duplicate_rows_fail(self):
        readme = synthetic_readme([("HOW_A", "x"), ("HOW_A", "x")])
        with pytest.raises(AssertionError, match="HOW_A has more than one row"):
            parse_readme_rules(readme)

    def test_entries_without_parameter_syntax_are_skipped(self):
        assert parse_parameters("Sem parâmetro numérico. Referência: a lista do STR") == []


class TestRealReadme:
    def test_readme_rules_table_matches_policy(self):
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        problems = readme_policy_divergences(readme_text, real_policy, implemented_rule_codes())
        assert problems == [], "\n".join(problems)

    def test_every_implemented_rule_is_declared_in_policy(self):
        undeclared = implemented_rule_codes() - declared_rule_codes(real_policy)
        assert undeclared == set(), f"implemented but not declared in policy.RULE_CODES: {sorted(undeclared)}"
