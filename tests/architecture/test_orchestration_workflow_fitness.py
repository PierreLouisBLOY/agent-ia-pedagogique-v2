from __future__ import annotations

import ast
import re
import tomllib
from dataclasses import fields
from pathlib import Path
from typing import get_type_hints

from backend.agent_runtime.contracts import ExecutorKind
from backend.agent_runtime.orchestration import (
    BASELINE_WORKFLOW_CATALOG,
    WorkflowResponsibilityDescriptor,
    WorkflowTopologyDescriptor,
)
from backend.agent_runtime.runtime import Plan

ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME = ROOT / "backend" / "agent_runtime"
ORCHESTRATION = AGENT_RUNTIME / "orchestration"
WORKFLOWS = ORCHESTRATION / "workflows"
RUNTIME = AGENT_RUNTIME / "runtime"


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


def _defined_class_names(root: Path) -> set[str]:
    return {
        node.name
        for path in _python_files(root)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }


def _called_names(root: Path) -> set[str]:
    names: set[str] = set()
    for path in _python_files(root):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                names.add(node.func.id)
    return names


def test_workflow_catalogue_is_confined_to_the_new_orchestration_package() -> None:
    assert ORCHESTRATION.is_dir()
    assert WORKFLOWS.is_dir()
    assert {path.name for path in WORKFLOWS.glob("*.py")} == {
        "__init__.py",
        "catalog.py",
        "model.py",
    }
    runtime_zones = {
        path.name
        for path in RUNTIME.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    }
    assert runtime_zones == {"planning", "state", "scheduling", "execution"}


def test_workflows_define_topologies_not_one_engine_per_workflow() -> None:
    class_names = _defined_class_names(WORKFLOWS)
    assert not any(re.fullmatch(r"WF\d+Engine", name) for name in class_names)
    assert "WorkflowEngine" not in class_names
    assert "GateEngine" not in class_names
    assert "ToolRegistry" not in class_names
    assert "ToolCallPolicy" not in class_names
    assert "StepRunner" not in class_names
    assert "PlanCompiler" not in class_names
    assert "WorkflowSelector" not in class_names
    assert "Orchestrator" not in class_names
    assert "Coordinator" not in class_names


def test_workflow_catalogue_imports_stay_provider_neutral_and_data_only() -> None:
    forbidden_roots = {
        "django",
        "fastapi",
        "flask",
        "httpx",
        "openai",
        "requests",
        "sqlalchemy",
        "sqlite3",
    }
    forbidden_backend_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
    )
    imported = {
        module
        for path in _python_files(WORKFLOWS)
        for module in _imported_modules(path)
    }
    assert not {module.split(".")[0] for module in imported} & forbidden_roots
    assert all(not module.startswith(forbidden_backend_prefixes) for module in imported)
    source = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(WORKFLOWS))
    for forbidden in ("PermissionScope", "AccessMatrix", "AgentInvocation", "RAG"):
        assert forbidden not in source


def test_workflow_catalogue_constructs_no_plan_step_or_invocation() -> None:
    calls = _called_names(WORKFLOWS)
    assert not calls & {"Plan", "StepSpec", "AgentInvocation"}
    assert {field.name for field in fields(WorkflowTopologyDescriptor)} == {
        "workflow_kind",
        "canonical_name",
        "purpose",
        "required_responsibilities",
        "optional_responsibilities",
        "ordering_constraints",
        "gate_profile",
        "parallel_profile",
        "min_parallel_branches",
        "join_responsibility",
        "revision_profile",
        "application_boundary",
        "overlay",
    }


def test_responsibility_metadata_grants_no_permission_or_concrete_route() -> None:
    assert {field.name for field in fields(WorkflowResponsibilityDescriptor)} == {
        "responsibility",
        "owner_agent",
        "allowed_capability_classes",
    }
    assert all(
        not hasattr(descriptor, attribute)
        for descriptor in BASELINE_WORKFLOW_CATALOG.all()
        for attribute in ("permission_scope", "access_mode", "execution_route", "use_case")
    )


def test_plan_workflow_kind_and_executor_vocabulary_are_unchanged() -> None:
    assert get_type_hints(Plan)["workflow_kind"] is str
    assert [item.value for item in ExecutorKind] == [
        "AG-02",
        "AG-03",
        "AG-04",
        "APPLICATION",
        "UTILITY",
        "RUNTIME",
    ]
    assert "AG-01" not in {item.value for item in ExecutorKind}
    assert "AG-05" not in {item.value for item in ExecutorKind}


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == []
