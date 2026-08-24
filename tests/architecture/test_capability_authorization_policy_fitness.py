from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "backend" / "agent_runtime" / "policy"
DECISION = POLICY / "capability_decision.py"
CONFIGURATION = POLICY / "policy_configuration.py"
D_FILES = (DECISION, CONFIGURATION)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_final_policy_imports_respect_runtime_boundaries() -> None:
    forbidden_prefixes = (
        "backend.modules",
        "backend.adapters",
        "backend.infrastructure",
        "backend.providers",
    )
    violations: list[str] = []

    for path in D_FILES:
        for node in ast.walk(_tree(path)):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = [node.module]
            violations.extend(
                f"{path.name}: {module}"
                for module in modules
                if module.startswith(forbidden_prefixes) or ".provider" in module.casefold()
            )

    assert violations == []


def test_decision_types_store_no_concrete_execution_binding() -> None:
    forbidden_fields = {
        "tool_id",
        "handler",
        "use_case_handler",
        "provider_payload",
        "fallback_capability",
        "alternative_agent",
    }
    fields_by_class = {
        node.name: {
            item.target.id
            for item in node.body
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
        }
        for node in _tree(DECISION).body
        if isinstance(node, ast.ClassDef) and node.name.endswith("Decision")
    }

    assert fields_by_class
    assert all(fields.isdisjoint(forbidden_fields) for fields in fields_by_class.values())


def test_final_policy_defines_no_deferred_engine_or_mutable_state() -> None:
    forbidden_classes = {
        "Scheduler",
        "RunState",
        "StepState",
        "GateEngine",
        "BudgetState",
        "ToolCallPolicy",
        "GrantRegistry",
        "ToolRegistry",
    }
    definitions = {
        node.name
        for path in D_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }

    assert definitions.isdisjoint(forbidden_classes)


def test_exactly_one_final_layer_combines_matrix_and_scope_evaluator() -> None:
    combiners = []
    for path in POLICY.glob("*.py"):
        imported_names = {
            alias.name
            for node in ast.walk(_tree(path))
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        if {"AccessMatrix", "PermissionScopeEvaluator"} <= imported_names:
            combiners.append(path.name)

    assert combiners == ["capability_decision.py"]


def test_c_scope_evaluator_remains_independent_of_access_matrix() -> None:
    source = (POLICY / "permission_evaluator.py").read_text(encoding="utf-8")

    assert "AccessMatrix" not in source
    assert "AccessMode" not in source


def test_matrix_deny_has_an_explicit_return_branch() -> None:
    evaluate = next(
        node
        for node in ast.walk(_tree(DECISION))
        if isinstance(node, ast.FunctionDef) and node.name == "evaluate"
    )
    deny_branches = [
        node
        for node in ast.walk(evaluate)
        if isinstance(node, ast.If)
        and "AccessMode.DENY" in ast.unparse(node.test)
        and any(isinstance(item, ast.Return) for item in node.body)
        and "MATRIX_DENY" in ast.unparse(node)
    ]

    assert len(deny_branches) == 1


def test_decision_api_has_no_fallback_or_autonomy_bypass() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in D_FILES)

    assert "fallback" not in source.casefold()
    assert "alternative_agent" not in source
    assert "RuntimeMode" not in source
    assert "AutonomyLevel" not in source


def test_project_runtime_dependencies_remain_empty_for_final_policy() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["dependencies"] == []
