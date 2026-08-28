from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "tests/support/retrieval_quality_cases.py"
REAL_GATE = ROOT / "tests/non_functional/test_retrieval_quality_real_gate.py"


def test_benchmark_uses_agent_boundary_without_parallel_sql_or_provider() -> None:
    paths = (CATALOG, REAL_GATE)
    forbidden_import_roots = {
        "anthropic",
        "openai",
        "sqlite3",
    }
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in (
                node.names
                if isinstance(node, ast.Import)
                else [ast.alias(name=node.module or "")]
            )
        }
        assert imports.isdisjoint(forbidden_import_roots)
        source = path.read_text(encoding="utf-8").lower()
        assert "select " not in source
        assert "insert " not in source
        assert ".execute(" not in source


def test_real_gate_uses_environment_only_and_no_private_seed_path() -> None:
    source = REAL_GATE.read_text(encoding="utf-8")
    assert "PEDAGOGICAL_CANONICAL_SEED_PATH" not in source
    assert "SEED_PATH_ENV" in source
    assert "G:\\" not in source
    assert "skip" not in source.lower()
