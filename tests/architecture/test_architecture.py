from pathlib import Path

import pytest

from tests.architecture.architecture_rules import find_violations

SRC = Path(__file__).resolve().parents[2] / "src"


def write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def rules_hit(root: Path) -> set:
    return {violation.rule for violation in find_violations(root)}


def test_real_source_tree_respects_the_layers():
    assert find_violations(SRC) == []


def test_clean_synthetic_tree_has_no_violation(tmp_path):
    write(tmp_path, "resources/pix.py", "from controllers import PixController\nfrom utils.schema_handler import SchemaHandler\n")
    write(tmp_path, "controllers/pix.py", "from repositories import PixRepository\nfrom models import Account\nfrom dtos import PixDTO\n")
    repository = "from sqlalchemy.exc import IntegrityError\nfrom models import Account\n\n\ndef get(s):\n    return s.query(Account).first()\n"
    write(tmp_path, "repositories/pix.py", repository)
    write(tmp_path, "engine/engine.py", "from datetime import datetime\nfrom src.engine.policy import X\n")
    assert find_violations(tmp_path) == []


@pytest.mark.parametrize("statement", [
    "from repositories import PixRepository",
    "from models import Account",
    "import repositories.pix",
    "from sqlalchemy.orm import Session",
    "from database import get_context",
    "from dtos import PixAnalysisDto",
    "from engine import evaluate",
    "from src.engine.engine import evaluate",
])
def test_resource_only_talks_to_the_controller(tmp_path, statement):
    write(tmp_path, "resources/pix.py", statement + "\n")
    assert rules_hit(tmp_path) == {"resource-imports-lower-layer"}


@pytest.mark.parametrize("statement", [
    "from sqlalchemy import select",
    "from sqlalchemy.exc import IntegrityError",
    "import sqlalchemy",
])
def test_controller_must_not_import_sqlalchemy(tmp_path, statement):
    write(tmp_path, "controllers/pix.py", statement + "\n")
    assert rules_hit(tmp_path) == {"controller-imports-sqlalchemy"}


def test_controller_must_not_import_session_even_for_type_hints(tmp_path):
    write(tmp_path, "controllers/base_controller.py", "from sqlalchemy.orm import Session\n")
    assert rules_hit(tmp_path) == {"controller-imports-sqlalchemy"}


def test_repository_must_not_call_the_engine(tmp_path):
    write(tmp_path, "repositories/pix.py", "from engine import evaluate\n")
    assert rules_hit(tmp_path) == {"lower-layer-imports-upper-layer"}


@pytest.mark.parametrize("layer", ["models", "repositories", "dtos"])
@pytest.mark.parametrize("statement", ["from controllers import PixController", "from resources import PixResource"])
def test_lower_layers_must_not_import_upper_layers(tmp_path, layer, statement):
    write(tmp_path, f"{layer}/thing.py", statement + "\n")
    assert rules_hit(tmp_path) == {"lower-layer-imports-upper-layer"}


def test_models_must_not_import_repositories_dtos_or_schemas(tmp_path):
    write(tmp_path, "models/account.py", "from repositories import AccountRepository\nfrom dtos import AccountDTO\n")
    assert rules_hit(tmp_path) == {"lower-layer-imports-upper-layer"}


@pytest.mark.parametrize("layer", ["resources", "controllers", "dtos", "models", "engine", "middlewares"])
def test_queries_outside_repositories_are_forbidden(tmp_path, layer):
    write(tmp_path, f"{layer}/thing.py", "def run(session):\n    return session.query(Account).first()\n")
    assert "query-outside-repository" in rules_hit(tmp_path)


@pytest.mark.parametrize("call", ["session.execute(statement)", "select(Account)", "session.scalars(statement)"])
def test_core_queries_outside_repositories_are_forbidden(tmp_path, call):
    write(tmp_path, "controllers/thing.py", f"def run(session):\n    return {call}\n")
    assert "query-outside-repository" in rules_hit(tmp_path)


def test_database_module_may_open_sessions(tmp_path):
    write(tmp_path, "database.py", "from sqlalchemy.orm import sessionmaker\nSessionLocal = sessionmaker()\n")
    assert find_violations(tmp_path) == []


@pytest.mark.parametrize("statement", [
    "import sqlalchemy",
    "from sqlalchemy.orm import Session",
    "import fastapi",
    "from fastapi import Request",
    "import requests",
    "import logging",
    "import os",
    "from repositories import PixRepository",
    "from controllers import PixController",
])
def test_engine_must_stay_pure_in_imports(tmp_path, statement):
    write(tmp_path, "engine/thing.py", statement + "\n")
    assert rules_hit(tmp_path) == {"engine-impure"}


@pytest.mark.parametrize("call", ["datetime.now()", "datetime.utcnow()", "datetime.today()", "time.time()", "print('x')"])
def test_engine_must_not_read_the_clock_or_print(tmp_path, call):
    write(tmp_path, "engine/thing.py", f"def run():\n    return {call}\n")
    assert rules_hit(tmp_path) == {"engine-impure"}


def test_engine_may_import_datetime_types_and_itself(tmp_path):
    imports = [
        "from datetime import datetime, timedelta",
        "from dataclasses import dataclass",
        "from src.engine.policy import X",
        "from engine.rules import fired",
        "from . import clock",
    ]
    write(tmp_path, "engine/thing.py", "\n".join(imports) + "\n")
    assert find_violations(tmp_path) == []


def test_violation_reports_file_and_line(tmp_path):
    write(tmp_path, "resources/pix.py", "import json\nfrom repositories import PixRepository\n")
    violation = find_violations(tmp_path)[0]
    assert violation.path.name == "pix.py"
    assert violation.line == 2
