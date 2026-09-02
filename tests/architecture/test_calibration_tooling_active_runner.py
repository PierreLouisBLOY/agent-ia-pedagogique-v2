from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLING = ROOT / "calibration_tooling"
BACKEND = ROOT / "backend"
HARNESS = ROOT / "evaluation_harness"
CONTRACTS = TOOLING / "contracts"
APPLICATION = TOOLING / "application"
HISTORICAL_IMPORT_ROOTS = (
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


def test_exactly_one_active_runner_and_one_active_parser_are_declared() -> None:
    runner_targets = tuple(
        path
        for path in _python_files(TOOLING)
        if "ACTIVE_RUNNER_TARGET:" in path.read_text(encoding="utf-8")
    )
    parser_targets = tuple(
        path
        for path in _python_files(TOOLING)
        if "ACTIVE_PARSER_TARGET:" in path.read_text(encoding="utf-8")
    )
    assert runner_targets == (TOOLING / "runtime/runner.py",)
    assert parser_targets == (TOOLING / "contracts/parser.py",)


def test_active_graph_has_no_import_to_historical_or_test_provider_code() -> None:
    imports = {
        module for path in _python_files(TOOLING) for module in _imports(path)
    }
    assert all(
        not module.startswith(HISTORICAL_IMPORT_ROOTS) for module in imports
    )
    assert all(not module.startswith("tests") for module in imports)


def test_backend_and_harness_do_not_import_calibration_tooling() -> None:
    for root in (BACKEND, HARNESS):
        imports = {
            module for path in _python_files(root) for module in _imports(path)
        }
        assert all(not module.startswith("calibration_tooling") for module in imports)


def test_contracts_and_application_have_no_provider_sdk_or_infrastructure_import() -> None:
    forbidden_roots = {
        "anthropic",
        "backend",
        "httpx",
        "openai",
        "requests",
        "socket",
        "sqlite3",
        "urllib",
    }
    imports = {
        module
        for root in (CONTRACTS, APPLICATION)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert {module.split(".")[0] for module in imports}.isdisjoint(forbidden_roots)


def test_active_code_has_no_typing_escape_or_legacy_compatibility_wrapper() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(TOOLING)
    )
    assert "typing import Any" not in source
    assert "# type: ignore" not in source
    assert "LEGACY_COMPAT" not in source
    assert "tests/calibration/pedagogical" not in source
    assert "tests/providers/anthropic" not in source


def test_b03_adds_only_the_anthropic_adapter_without_preempting_b04() -> None:
    adapter = TOOLING / "adapters/anthropic"
    assert adapter.is_dir()
    assert {path.name for path in adapter.glob("*.py")} == {
        "__init__.py",
        "contracts.py",
        "mapping.py",
        "parser.py",
        "scorer.py",
        "transport.py",
    }
    assert not (TOOLING / "runtime/composition.py").exists()
    assert not (TOOLING / "runtime/cli.py").exists()
