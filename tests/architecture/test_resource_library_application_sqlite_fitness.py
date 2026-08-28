from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "backend/modules/resource_library"
INBOUND = ROOT / "backend/adapters/inbound/application/resource_library.py"
OUTBOUND = ROOT / "backend/adapters/outbound/resource_library/sqlite.py"
E2E = ROOT / "tests/e2e/core/resource_adapters.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_m03_application_and_inbound_boundary_have_no_storage_dependency() -> None:
    for path in MODULE.rglob("*.py"):
        imports = _imports(path)
        assert "sqlite3" not in imports
        assert not any(item.startswith("backend.adapters") for item in imports)
    assert "sqlite3" not in _imports(INBOUND)
    assert "backend.adapters.outbound" not in _imports(INBOUND)


def test_sqlite_mapping_is_outbound_and_reuses_c0_op03_without_duplicate_sql() -> None:
    source = OUTBOUND.read_text(encoding="utf-8")
    assert "ResourceStore" in source
    assert "load_resource" in source
    for token in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "PRAGMA "):
        assert token not in source.upper()


def test_scn01_binding_has_no_sql_or_direct_sqlite_dependency() -> None:
    source = E2E.read_text(encoding="utf-8")
    assert "sqlite3" not in _imports(E2E)
    for token in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "PRAGMA "):
        assert token not in source.upper()


def test_backend_never_imports_the_test_only_scn01_binding() -> None:
    for path in (ROOT / "backend").rglob("*.py"):
        assert not any(
            imported == "tests.e2e" or imported.startswith("tests.e2e.")
            for imported in _imports(path)
        ), path
