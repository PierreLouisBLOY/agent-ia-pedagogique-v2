from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_AGENT = ROOT / "backend/agent_runtime/agents/evidence/evidence_agent.py"
SQLITE_EVIDENCE = ROOT / "backend/adapters/outbound/evidence/sqlite.py"
E2E_ADAPTER = ROOT / "tests/e2e/core/adapters.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_evidence_agent_and_agent_runtime_are_storage_and_harness_independent() -> None:
    assert "sqlite3" not in _imports(EVIDENCE_AGENT)
    for path in (ROOT / "backend/agent_runtime").rglob("*.py"):
        assert not any(
            imported == "evaluation_harness"
            or imported.startswith("evaluation_harness.")
            for imported in _imports(path)
        ), path


def test_sqlite_evidence_binding_is_outbound_and_provider_free() -> None:
    assert SQLITE_EVIDENCE.is_file()
    imports = _imports(SQLITE_EVIDENCE)
    forbidden_roots = {
        "evaluation_harness",
        "tests",
        "openai",
        "anthropic",
        "google.generativeai",
        "requests",
        "httpx",
        "urllib",
    }
    assert not any(
        imported == root or imported.startswith(f"{root}.")
        for imported in imports
        for root in forbidden_roots
    )
    source = SQLITE_EVIDENCE.read_text(encoding="utf-8")
    assert "sqlite3.Row" not in source
    assert "SearchHit" in source
    assert "ContentFragment" not in source


def test_e2e_adapter_has_no_sql_or_direct_sqlite_dependency() -> None:
    source = E2E_ADAPTER.read_text(encoding="utf-8")
    assert "sqlite3" not in _imports(E2E_ADAPTER)
    for token in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "PRAGMA "):
        assert token not in source.upper()


def test_backend_never_imports_test_only_e2e_bindings() -> None:
    for path in (ROOT / "backend").rglob("*.py"):
        assert not any(
            imported == "tests.e2e" or imported.startswith("tests.e2e.")
            for imported in _imports(path)
        ), path
