import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional

LOWER_LAYER_FORBIDDEN_IMPORTS = {
    "models": {"controllers", "resources", "repositories", "dtos", "schemas"},
    "repositories": {"controllers", "resources", "dtos", "engine"},
    "dtos": {"controllers", "resources", "repositories"},
}
RESOURCE_FORBIDDEN_IMPORTS = {"repositories", "models", "sqlalchemy", "database", "dtos", "engine"}
ENGINE_FORBIDDEN_IMPORTS = {
    "sqlalchemy", "fastapi", "starlette", "requests", "httpx", "os", "logging", "time",
    "repositories", "controllers", "resources", "models", "dtos", "database", "middlewares", "connectors",
}
ENGINE_FORBIDDEN_CALLS = {("datetime", "now"), ("datetime", "utcnow"), ("datetime", "today"), ("date", "today"), ("time", "time")}
QUERY_ATTRIBUTES = {"query", "execute", "scalars", "scalar"}
QUERY_EXEMPT_FILES = {"database.py"}


@dataclass(frozen=True)
class Violation:
    rule: str
    path: Path
    line: int
    detail: str


@dataclass(frozen=True)
class ImportedName:
    module: str
    name: Optional[str]
    line: int


def normalize(module: str) -> str:
    return module[len("src."):] if module.startswith("src.") else module


def imported_names(tree: ast.AST) -> Iterator[ImportedName]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield ImportedName(normalize(alias.name), None, node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for alias in node.names:
                yield ImportedName(normalize(node.module), alias.name, node.lineno)


def top_package(module: str) -> str:
    return module.split(".")[0]


def layer_of(path: Path, root: Path) -> Optional[str]:
    relative = path.relative_to(root)
    return relative.parts[0] if len(relative.parts) > 1 else None


def is_query_call(node: ast.Call) -> bool:
    function = node.func
    if isinstance(function, ast.Attribute):
        return function.attr in QUERY_ATTRIBUTES or function.attr == "select"
    return isinstance(function, ast.Name) and function.id == "select"


def is_forbidden_engine_call(node: ast.Call) -> bool:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id == "print"
    if isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
        return (function.value.id, function.attr) in ENGINE_FORBIDDEN_CALLS
    return False


def import_violations(layer: Optional[str], names: List[ImportedName], path: Path) -> Iterator[Violation]:
    for item in names:
        top = top_package(item.module)
        if layer == "resources" and top in RESOURCE_FORBIDDEN_IMPORTS:
            yield Violation("resource-imports-lower-layer", path, item.line, item.module)
        elif layer == "controllers" and top == "sqlalchemy":
            yield Violation("controller-imports-sqlalchemy", path, item.line, item.module)
        elif layer in LOWER_LAYER_FORBIDDEN_IMPORTS and top in LOWER_LAYER_FORBIDDEN_IMPORTS[layer]:
            yield Violation("lower-layer-imports-upper-layer", path, item.line, item.module)
        elif layer == "engine" and top in ENGINE_FORBIDDEN_IMPORTS:
            yield Violation("engine-impure", path, item.line, item.module)


def call_violations(layer: Optional[str], tree: ast.AST, path: Path) -> Iterator[Violation]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if layer != "repositories" and path.name not in QUERY_EXEMPT_FILES and is_query_call(node):
            yield Violation("query-outside-repository", path, node.lineno, ast.unparse(node.func))
        if layer == "engine" and is_forbidden_engine_call(node):
            yield Violation("engine-impure", path, node.lineno, ast.unparse(node.func))


def find_violations(root: Path) -> List[Violation]:
    violations: List[Violation] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        layer = layer_of(path, root)
        violations.extend(import_violations(layer, list(imported_names(tree)), path))
        violations.extend(call_violations(layer, tree, path))
    return violations
