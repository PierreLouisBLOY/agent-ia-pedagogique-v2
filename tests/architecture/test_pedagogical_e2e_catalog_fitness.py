from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from backend.agent_runtime.orchestration.workflows import WorkflowKind
from evaluation_harness import EvaluationTargetKind
from tests.e2e.core.catalog import (
    CANONICAL_PEDAGOGICAL_SCENARIOS,
    CanonicalPedagogicalScenario,
)

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
HARNESS = ROOT / "evaluation_harness"
E2E_CORE = ROOT / "tests" / "e2e" / "core"
PROVIDERS = ROOT / "tests" / "providers"
DECLARATION_MODULES = (
    E2E_CORE / "catalog.py",
    E2E_CORE / "expectations.py",
    E2E_CORE / "fixtures.py",
)


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_backend_and_harness_never_import_pedagogical_e2e() -> None:
    for root in (BACKEND, HARNESS):
        assert all(
            not module.startswith("tests.e2e")
            for path in _python_files(root)
            for module in _imports(path)
        )


def test_declaration_dependencies_stay_on_the_approved_test_only_boundary() -> None:
    allowed_roots = {
        "__future__",
        "backend",
        "dataclasses",
        "enum",
        "evaluation_harness",
        "re",
        "tests",
    }
    imports = {module for path in DECLARATION_MODULES for module in _imports(path)}
    assert {module.split(".")[0] for module in imports} <= allowed_roots
    backend_imports = {module for module in imports if module.startswith("backend")}
    assert backend_imports == {"backend.agent_runtime.orchestration.workflows"}
    assert not any(module.startswith("tests.support") for module in imports)


def test_no_provider_network_database_or_yaml_dependency_exists() -> None:
    forbidden_roots = {
        "anthropic",
        "boto3",
        "google",
        "httpx",
        "openai",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "urllib",
        "yaml",
    }
    imports = {module for path in DECLARATION_MODULES for module in _imports(path)}
    assert {module.split(".")[0] for module in imports}.isdisjoint(forbidden_roots)
    with (ROOT / "pyproject.toml").open("rb") as stream:
        assert tomllib.load(stream)["project"]["dependencies"] == []


def test_no_raw_golden_snapshot_or_business_fixture_file_exists() -> None:
    forbidden_suffixes = (
        ".db",
        ".golden.txt",
        ".sqlite",
        ".snap",
        ".yaml",
        ".yml",
    )
    files = tuple(path for path in E2E_CORE.rglob("*") if path.is_file())
    assert all(not path.name.endswith(forbidden_suffixes) for path in files)
    assert {path.name for path in DECLARATION_MODULES} <= {path.name for path in files}


def test_declaration_modules_never_execute_the_evaluation_runner_or_runtime_owners() -> None:
    forbidden_imports = {
        "EvaluationRunner",
        "EvaluationTargetExecutorPort",
        "GeneratorAgent",
        "EvidenceAgent",
        "ReviewerAgent",
        "PlanExecutor",
    }
    forbidden_calls = {"run_case", "run_suite", "execute", "execute_cycle"}
    for path in DECLARATION_MODULES:
        tree = _tree(path)
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert imported_names.isdisjoint(forbidden_imports)
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in forbidden_calls
            for node in ast.walk(tree)
        )


def test_workflows_are_reused_from_the_closed_runtime_enum_without_clone() -> None:
    class_names = {
        node.name
        for path in DECLARATION_MODULES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert "PedagogicalWorkflowKind" not in class_names
    assert not any(name.endswith("WorkflowKind") for name in class_names)
    assert {
        workflow
        for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS
        for workflow in scenario.workflow_kinds
    } == set(WorkflowKind)


def test_catalog_exposes_test_metadata_without_new_runtime_authority() -> None:
    forbidden_fields = {
        "agent",
        "allow",
        "approve",
        "authority",
        "capability",
        "gate_decision",
        "handler",
        "permission",
        "runtime_level",
        "tool",
        "use_case",
    }
    field_names = {
        node.target.id
        for node in ast.walk(_tree(E2E_CORE / "catalog.py"))
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert field_names.isdisjoint(forbidden_fields)
    assert all(
        scenario.case.target.kind is EvaluationTargetKind.WORKFLOW
        for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS
    )
    assert not hasattr(CanonicalPedagogicalScenario, "capability_id")


def test_provider_scaffold_remains_outside_b() -> None:
    assert tuple(sorted(path.name for path in PROVIDERS.iterdir() if path.is_file())) == (
        ".gitkeep",
    )
    assert not (E2E_CORE / "__init__.py").exists()
