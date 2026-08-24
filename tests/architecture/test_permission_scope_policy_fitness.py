from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "backend" / "agent_runtime" / "policy"
CONTRACT = ROOT / "backend" / "agent_runtime" / "contracts" / "policy" / "permission_scope.py"
C_POLICY_FILES = (
    POLICY / "permission_vocabulary.py",
    POLICY / "permission_evaluator.py",
    POLICY / "scope_narrowing.py",
    POLICY / "delegation_policy.py",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_permission_scope_contract_remains_data_only() -> None:
    class_node = next(
        node
        for node in _tree(CONTRACT).body
        if isinstance(node, ast.ClassDef) and node.name == "PermissionScope"
    )
    methods = {node.name for node in class_node.body if isinstance(node, ast.FunctionDef)}

    assert methods == {"__post_init__"}
    assert methods.isdisjoint({"allows", "evaluate", "grant", "merge"})


def test_permission_policy_imports_respect_runtime_boundaries() -> None:
    forbidden_prefixes = (
        "backend.modules",
        "backend.adapters",
        "backend.infrastructure",
        "backend.providers",
    )
    violations: list[str] = []

    for path in C_POLICY_FILES:
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


def test_c_policy_defines_no_deferred_runtime_engine_or_state() -> None:
    forbidden_classes = {
        "GrantRegistry",
        "Scheduler",
        "RunState",
        "StepState",
        "ToolCallPolicy",
        "GateEngine",
        "BudgetState",
    }
    definitions = {
        node.name
        for path in C_POLICY_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }

    assert definitions.isdisjoint(forbidden_classes)


def test_scope_and_delegation_evaluators_do_not_consult_access_matrix() -> None:
    checked = (POLICY / "permission_evaluator.py", POLICY / "delegation_policy.py")
    source = "\n".join(path.read_text(encoding="utf-8") for path in checked)

    assert "BASELINE_AGENT_CAPABILITY_MATRIX" not in source
    assert "AccessMatrix" not in source
    assert "AccessMode" not in source


def test_runtime_mode_and_autonomy_are_absent_from_permission_inputs() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in C_POLICY_FILES)

    assert "RuntimeMode" not in source
    assert "AutonomyLevel" not in source


def test_only_the_scoped_permission_evaluator_is_added() -> None:
    evaluator_definitions = [
        (path.relative_to(ROOT).as_posix(), node.name)
        for path in (ROOT / "backend" / "agent_runtime").rglob("*.py")
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and "Evaluator" in node.name
    ]

    assert evaluator_definitions == [
        (
            "backend/agent_runtime/policy/permission_evaluator.py",
            "PermissionScopeEvaluator",
        )
    ]


def test_project_runtime_dependencies_remain_empty_for_permission_policy() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["dependencies"] == []
