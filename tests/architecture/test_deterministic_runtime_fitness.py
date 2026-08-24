from __future__ import annotations

import ast
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.contracts import StepSpec
from backend.agent_runtime.runtime import Plan, RunState

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
RUNTIME = BACKEND / "agent_runtime" / "runtime"
MODULES = BACKEND / "modules"


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


def test_runtime_state_and_plan_have_exact_technical_locations() -> None:
    definitions = {
        node.name: path.relative_to(ROOT).as_posix()
        for path in _python_files(RUNTIME)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
        and node.name in {"Plan", "StepState", "RunState"}
    }

    assert definitions == {
        "Plan": "backend/agent_runtime/runtime/planning/plan.py",
        "StepState": "backend/agent_runtime/runtime/state/step_state.py",
        "RunState": "backend/agent_runtime/runtime/state/run_state.py",
    }


def test_domain_application_and_modules_do_not_own_runtime_state() -> None:
    forbidden_roots = (
        BACKEND / "domain",
        BACKEND / "application",
        MODULES,
    )
    definitions = [
        f"{path.relative_to(ROOT).as_posix()}: {node.name}"
        for root in forbidden_roots
        if root.exists()
        for path in _python_files(root)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
        and node.name in {"Plan", "StepState", "RunState"}
    ]

    assert definitions == []


def test_runtime_imports_respect_deterministic_boundary() -> None:
    forbidden_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
        "backend.providers",
    )
    violations = [
        f"{path.relative_to(ROOT).as_posix()}: {module}"
        for path in _python_files(RUNTIME)
        for module in _imported_modules(path)
        if module.startswith(forbidden_prefixes) or ".provider" in module.casefold()
    ]

    assert violations == []


def test_runtime_uses_only_stdlib_and_backend_import_roots() -> None:
    allowed_roots = {
        "__future__",
        "backend",
        "collections",
        "dataclasses",
        "enum",
        "types",
    }
    imported_roots = {
        module.split(".", maxsplit=1)[0]
        for path in _python_files(RUNTIME)
        for module in _imported_modules(path)
    }

    assert imported_roots <= allowed_roots


def test_deferred_runtime_components_are_not_implemented() -> None:
    forbidden_classes = {
        "Scheduler",
        "PlanExecutor",
        "GateEngine",
        "BudgetState",
        "StateSnapshotStore",
        "ToolCallPolicy",
    }
    class_names = {
        node.name
        for path in _python_files(BACKEND)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }

    assert class_names.isdisjoint(forbidden_classes)
    assert not (RUNTIME / "scheduler.py").exists()
    assert not (RUNTIME / "executor.py").exists()


def test_runtime_contains_no_concrete_execution_binding() -> None:
    forbidden_fields = {"handler", "tool_id", "use_case_handler", "provider"}
    declared_fields = {
        item.target.id
        for path in _python_files(RUNTIME)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
        for item in node.body
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
    }

    assert declared_fields.isdisjoint(forbidden_fields)


def test_workflow_catalogue_is_not_anticipated() -> None:
    workflow_kind_definitions = [
        path.relative_to(ROOT).as_posix()
        for path in _python_files(BACKEND)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == "WorkflowKind"
    ]
    runtime_string_literals = {
        node.value
        for path in _python_files(RUNTIME)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert workflow_kind_definitions == []
    assert all(not value.startswith("WF-") for value in runtime_string_literals)


def test_declarative_and_runtime_models_do_not_duplicate_state_or_edges() -> None:
    step_spec_fields = {item.name for item in fields(StepSpec)}
    plan_fields = {item.name for item in fields(Plan)}
    run_state_fields = {item.name for item in fields(RunState)}

    assert "status" not in step_spec_fields
    assert "dependencies" not in plan_fields
    assert "current_step_id" not in run_state_fields


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["dependencies"] == []
