from __future__ import annotations

import ast
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.runtime import Plan

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
RUNTIME = BACKEND / "agent_runtime" / "runtime"
PLANNING = RUNTIME / "planning"
REVISION = PLANNING / "revision.py"


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


def _function(name: str) -> ast.FunctionDef:
    return next(
        node
        for node in ast.walk(_tree(REVISION))
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_plan_revision_types_are_confined_to_runtime_planning_revision() -> None:
    names = {
        "PlanHistory",
        "PlanRevisionCode",
        "PlanRevisionEngine",
        "PlanRevisionIssue",
        "PlanRevisionResult",
    }
    definitions = {
        node.name: path.relative_to(ROOT).as_posix()
        for path in _python_files(BACKEND)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name in names
    }

    assert definitions == {
        name: "backend/agent_runtime/runtime/planning/revision.py" for name in names
    }


def test_revision_imports_respect_runtime_boundaries() -> None:
    forbidden_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
        "backend.providers",
    )
    imports = _imported_modules(REVISION)

    assert all(not module.startswith(forbidden_prefixes) for module in imports)
    assert all("provider" not in module.casefold() for module in imports)


def test_revision_has_no_db_http_orm_filesystem_or_concurrency_dependency() -> None:
    forbidden_roots = {
        "aiohttp",
        "asyncio",
        "django",
        "fastapi",
        "flask",
        "multiprocessing",
        "pathlib",
        "sqlalchemy",
        "sqlite3",
        "threading",
    }
    imported_roots = {
        module.split(".", maxsplit=1)[0] for module in _imported_modules(REVISION)
    }
    calls = {
        node.func.id
        for node in ast.walk(_tree(REVISION))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert imported_roots.isdisjoint(forbidden_roots)
    assert calls.isdisjoint({"open", "exec", "eval"})


def test_revision_constructs_no_plan_or_deferred_runtime_component() -> None:
    forbidden_symbols = {
        "AgentInvocation",
        "BudgetState",
        "GateEngine",
        "StateSnapshotStore",
        "ToolCallPolicy",
        "ToolRegistry",
    }
    tree = _tree(REVISION)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    symbols = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    assert "Plan" not in calls
    assert symbols.isdisjoint(forbidden_symbols)


def test_revision_does_not_anticipate_agent_planner_or_workflow_catalogue() -> None:
    strings = {
        node.value
        for node in ast.walk(_tree(REVISION))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert all(not value.startswith("WF-") for value in strings)
    assert "AG-01" not in strings
    assert all("llm" not in value.casefold() for value in strings)


def test_execution_identity_has_exact_semantic_fields_and_ignores_controls() -> None:
    identity = _function("_step_execution_identity")
    attributes = {
        node.attr
        for node in ast.walk(identity)
        if isinstance(node, ast.Attribute)
    }

    assert attributes == {
        "kind",
        "capability_id",
        "executor",
        "objective",
        "input_refs",
        "depends_on",
        "success_criteria",
        "output_contract",
        "parallel_group",
    }
    assert attributes.isdisjoint(
        {"step_id", "permission_scope_ref", "budget", "failure_policy"}
    )


def test_no_progress_signature_uses_step_order_and_execution_identity() -> None:
    signature = _function("_plan_execution_signature")
    attributes = {
        node.attr
        for node in ast.walk(signature)
        if isinstance(node, ast.Attribute)
    }
    calls = {
        node.func.id
        for node in ast.walk(signature)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert attributes == {"steps", "step_id"}
    assert "_step_execution_identity" in calls
    assert attributes.isdisjoint(
        {
            "plan_version",
            "budget_envelope",
            "permission_scope_ref",
            "failure_policy",
            "risk_profile",
            "assumptions",
        }
    )


def test_revision_reuses_plan_validator_instead_of_duplicating_validation() -> None:
    tree = _tree(REVISION)
    class_names = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    }
    imported_symbols = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    validate_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "validate"
    ]

    assert "PlanValidator" in imported_symbols
    assert "PlanValidator" not in class_names
    assert len(validate_calls) == 1


def test_revision_uses_policy_max_plan_versions_without_local_limit() -> None:
    tree = _tree(REVISION)
    policy_limits = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "max_plan_versions"
    ]

    assert len(policy_limits) == 1


def test_revision_contains_no_retry_backoff_merge_or_repository_behavior() -> None:
    tree = _tree(REVISION)
    defined_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }

    assert all(
        fragment not in name.casefold()
        for name in defined_names
        for fragment in ("retry", "backoff", "merge", "repository", "provider")
    )
    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))


def test_plan_remains_frozen_and_runtime_dependencies_remain_empty() -> None:
    params = Plan.__dataclass_params__

    assert params.frozen
    assert "plan_version" in {item.name for item in fields(Plan)}
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]
    assert project["dependencies"] == []
