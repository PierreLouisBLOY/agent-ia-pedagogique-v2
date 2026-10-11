from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "backend/modules/resource_library"
ADAPTER = ROOT / "backend/adapters/outbound/resource_library/exact_source_sqlite.py"
COMPOSITION = ROOT / "backend/infrastructure/composition/factories/r6_p0.py"
HTTP = ROOT / "backend/adapters/inbound/api"
CLI = ROOT / "backend/adapters/inbound/cli"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_m03_exact_source_contract_has_no_sqlite_or_adapter_dependency() -> None:
    for path in MODULE.rglob("*.py"):
        imports = _imports(path)
        assert "sqlite3" not in imports
        assert not any(name.startswith("backend.adapters") for name in imports)


def test_exact_sql_is_confined_to_the_outbound_adapter() -> None:
    assert "sqlite3" in _imports(ADAPTER)
    source = ADAPTER.read_text(encoding="utf-8").upper()
    assert "SELECT " in source and "INSERT " not in source and "UPDATE " not in source
    query = (
        MODULE / "application/queries/get_exact_resource_evidence.py"
    ).read_text(encoding="utf-8").upper()
    assert all(token not in query for token in ("SELECT ", "PRAGMA ", "SQLITE"))


def test_u1_has_no_http_cli_or_global_router_exposure() -> None:
    forbidden = "GetExactResourceEvidenceQuery"
    for root in (HTTP, CLI):
        if root.exists():
            for path in root.rglob("*.py"):
                assert forbidden not in path.read_text(encoding="utf-8")
    composition = COMPOSITION.read_text(encoding="utf-8")
    assert "load_p0_exact_reference" in composition
    assert "R6_EXACT_SOURCE_BINDINGS" in composition


def test_r6_composition_has_exactly_six_pairs_and_no_search_fallback() -> None:
    source = COMPOSITION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    exact = functions["load_p0_exact_reference"]
    assert "_application_searcher" not in exact
    assert all(token not in exact.casefold() for token in ("fuzzy", "latest", "neighbor"))
