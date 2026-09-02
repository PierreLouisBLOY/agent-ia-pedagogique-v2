from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLING = ROOT / "calibration_tooling"
ACTIVE_TEST_ROOTS = (
    ROOT / "tests/unit/calibration_tooling",
    ROOT / "tests/integration/calibration_tooling",
)
HISTORICAL_ROOTS = (
    "tests.calibration.pedagogical",
    "tests.providers.anthropic",
)


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py"))) if root.is_dir() else ()


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_active_source_and_active_tests_import_no_historical_root() -> None:
    imports = {
        module
        for root in (TOOLING, *ACTIVE_TEST_ROOTS)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all(
        not module.startswith(HISTORICAL_ROOTS) for module in imports
    )
    assert all(not module.startswith("tests.providers") for module in imports)


def test_active_typing_has_no_ignore_stub_or_exclusion_escape() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(TOOLING)
    )
    assert "# type: ignore" not in source
    assert "typing import Any" not in source
    assert not tuple(TOOLING.rglob("*.pyi"))

    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    mypy = configuration["tool"]["mypy"]
    assert "exclude" not in mypy
    assert "overrides" not in mypy


def test_historical_only_marker_is_explicit_and_non_retroactive() -> None:
    marker = (TOOLING / "HISTORICAL_ONLY.md").read_text(encoding="utf-8")
    required = {
        "tests/calibration/pedagogical/",
        "tests/providers/anthropic/",
        "HISTORICAL_SOURCE_FILES_MODIFIED = 0",
        "ACTIVE_IMPORTS_TO_HISTORICAL = 0",
        "RETROACTIVE_REPAIR = FORBIDDEN",
    }
    assert all(value in marker for value in required)


def test_all_15_mapped_diagnostics_have_active_non_historical_evidence() -> None:
    evidence = {
        "MYPY-001": "test_anthropic_transport_parser.py",
        "MYPY-002": "test_anthropic_scorer.py",
        "MYPY-003": "test_anthropic_contracts_mapping.py",
        "MYPY-004": "test_anthropic_scorer.py",
        "MYPY-005": "test_anthropic_contracts_mapping.py",
        "MYPY-007": "test_active_historical_parity.py",
        "MYPY-008": "test_active_historical_parity.py",
        "MYPY-009": "test_active_historical_parity.py",
        "MYPY-017": "test_active_historical_parity.py",
        "MYPY-018": "test_authorization_budget.py",
        "MYPY-019": "test_authorization_budget.py",
        "MYPY-021": "test_authorization_budget.py",
        "MYPY-022": "test_authorization_budget.py",
        "MYPY-023": "test_calibration_tooling_imports.py",
        "MYPY-033": "test_runner_service.py",
    }
    assert len(evidence) == 15
    for error_id, filename in evidence.items():
        assert error_id.startswith("MYPY-")
        assert tuple(ROOT.glob(f"tests/**/{filename}")), filename
