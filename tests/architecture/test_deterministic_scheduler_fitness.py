from __future__ import annotations

import ast
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.contracts import StepSpec

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
RUNTIME = BACKEND / "agent_runtime" / "runtime"
SCHEDULING = RUNTIME / "scheduling"


def _python_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_modules(path: Path) -> tuple[str, ...]:
    modules: list[str] = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    return tuple(modules)


def test_scheduler_is_confined_to_runtime_scheduling_zone() -> None:
    definitions = {
        node.name: path.relative_to(ROOT).as_posix()
        for path in _python_files(RUNTIME)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
        and node.name in {
            "DependencyDisposition",
            "DeterministicScheduler",
            "SchedulerStateError",
            "SchedulingDecision",
        }
    }

    assert definitions == {
        "DependencyDisposition": "backend/agent_runtime/runtime/scheduling/scheduler.py",
        "DeterministicScheduler": "backend/agent_runtime/runtime/scheduling/scheduler.py",
        "SchedulerStateError": "backend/agent_runtime/runtime/scheduling/scheduler.py",
        "SchedulingDecision": "backend/agent_runtime/runtime/scheduling/scheduler.py",
    }
    assert {path.name for path in SCHEDULING.glob("*.py")} == {
        "__init__.py",
        "deadlines.py",
        "scheduler.py",
    }


def test_scheduler_imports_respect_runtime_boundaries() -> None:
    forbidden_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
        "backend.providers",
    )
    violations = [
        f"{path.relative_to(ROOT).as_posix()}: {module}"
        for path in _python_files(SCHEDULING)
        for module in _imported_modules(path)
        if module.startswith(forbidden_prefixes) or ".provider" in module.casefold()
    ]

    assert violations == []


def test_scheduler_uses_no_concurrency_or_third_party_runtime() -> None:
    forbidden_roots = {"asyncio", "multiprocessing", "threading"}
    allowed_roots = {
        "__future__",
        "backend",
        "dataclasses",
        "datetime",
        "enum",
    }
    imported_roots = {
        module.split(".", maxsplit=1)[0]
        for path in _python_files(SCHEDULING)
        for module in _imported_modules(path)
    }

    assert imported_roots.isdisjoint(forbidden_roots)
    assert imported_roots <= allowed_roots


def test_scheduler_defines_no_execution_or_deferred_engine() -> None:
    forbidden_classes = {
        "PlanExecutor",
        "StepRunner",
        "GateEngine",
        "BudgetState",
    }
    class_names = {
        node.name
        for path in _python_files(BACKEND)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }

    assert class_names.isdisjoint(forbidden_classes)


def test_scheduler_constructs_no_execution_contract_or_policy() -> None:
    forbidden_symbols = {
        "AgentInvocation",
        "DelegationEnvelope",
        "ToolCallRequest",
        "UseCaseRequest",
        "CapabilityAuthorizationPolicy",
        "PermissionScopeEvaluator",
    }
    referenced_symbols = {
        node.id
        for path in _python_files(SCHEDULING)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Name)
    }
    imported_symbols = {
        alias.name
        for path in _python_files(SCHEDULING)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert referenced_symbols.isdisjoint(forbidden_symbols)
    assert imported_symbols.isdisjoint(forbidden_symbols)


def test_scheduler_does_not_anticipate_workflow_catalogue() -> None:
    workflow_kind_definitions = [
        path.relative_to(ROOT).as_posix()
        for path in _python_files(BACKEND)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == "WorkflowKind"
    ]
    scheduling_strings = {
        node.value
        for path in _python_files(SCHEDULING)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert workflow_kind_definitions == []
    assert all(not value.startswith("WF-") for value in scheduling_strings)


def test_step_spec_remains_declarative_without_runtime_status() -> None:
    assert "status" not in {item.name for item in fields(StepSpec)}


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["dependencies"] == []
