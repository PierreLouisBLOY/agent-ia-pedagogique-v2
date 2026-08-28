from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.contracts import StepSpec

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
RUNTIME = BACKEND / "agent_runtime" / "runtime"
EXECUTION = RUNTIME / "execution"
EXECUTOR = EXECUTION / "executor.py"


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


def test_executor_contracts_are_confined_to_runtime_execution() -> None:
    expected = {
        "ExecutionCycleResult": "backend/agent_runtime/runtime/execution/executor.py",
        "ExecutionDirective": "backend/agent_runtime/runtime/execution/directives.py",
        "ExecutionDirectiveCode": "backend/agent_runtime/runtime/execution/directives.py",
        "PlanExecutor": "backend/agent_runtime/runtime/execution/executor.py",
        "PreLaunchDecision": "backend/agent_runtime/runtime/execution/prelaunch.py",
        "PreLaunchDisposition": "backend/agent_runtime/runtime/execution/prelaunch.py",
        "PreLaunchGuard": "backend/agent_runtime/runtime/execution/prelaunch.py",
        "StepExecutionResult": "backend/agent_runtime/runtime/execution/runner.py",
        "StepRunner": "backend/agent_runtime/runtime/execution/runner.py",
    }
    definitions = {
        node.name: path.relative_to(ROOT).as_posix()
        for path in _python_files(BACKEND)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name in expected
    }

    assert definitions == expected
    assert {path.name for path in EXECUTION.glob("*.py")} == {
        "__init__.py",
        "directives.py",
        "executor.py",
        "prelaunch.py",
        "runner.py",
    }


def test_executor_imports_respect_runtime_boundary() -> None:
    forbidden_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
        "backend.providers",
    )
    violations = [
        f"{path.relative_to(ROOT).as_posix()}: {module}"
        for path in _python_files(EXECUTION)
        for module in _imported_modules(path)
        if module.startswith(forbidden_prefixes) or ".provider" in module.casefold()
    ]

    assert violations == []


def test_executor_uses_no_http_orm_sql_or_concurrency_runtime() -> None:
    forbidden_roots = {
        "aiohttp",
        "asyncio",
        "django",
        "fastapi",
        "flask",
        "multiprocessing",
        "sqlalchemy",
        "sqlite3",
        "threading",
    }
    imported_roots = {
        module.split(".", maxsplit=1)[0]
        for path in _python_files(EXECUTION)
        for module in _imported_modules(path)
    }

    assert imported_roots.isdisjoint(forbidden_roots)


def test_runner_and_guard_are_protocols_without_production_implementation() -> None:
    protocol_names = {"PreLaunchGuard", "StepRunner"}
    protocol_definitions: dict[str, tuple[str, ...]] = {}
    concrete_implementations: list[str] = []
    for path in _python_files(EXECUTION):
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = tuple(
                base.id for base in node.bases if isinstance(base, ast.Name)
            )
            if node.name in protocol_names:
                protocol_definitions[node.name] = bases
            elif any(base in protocol_names for base in bases):
                concrete_implementations.append(node.name)

    assert protocol_definitions == {
        "PreLaunchGuard": ("Protocol",),
        "StepRunner": ("Protocol",),
    }
    assert concrete_implementations == []


def test_executor_does_not_embed_deferred_policy_engines() -> None:
    forbidden_symbols = {
        "BudgetState",
        "CapabilityAuthorizationPolicy",
        "GateEngine",
        "PermissionScopeEvaluator",
        "PermissionScopeResolver",
        "ToolCallPolicy",
        "ToolRegistry",
    }
    symbols = {
        node.id
        for path in _python_files(EXECUTION)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Name)
    }

    assert symbols.isdisjoint(forbidden_symbols)


def test_post_runner_contract_violations_converge_to_reconciliation() -> None:
    required_reasons = {
        "RUNNER_RESULT_CONTRACT_INVALID_EFFECT_UNKNOWN",
        "RUNNER_ERROR_STEP_MISMATCH_EFFECT_UNKNOWN",
        "RUNNER_ERROR_ATTEMPT_MISMATCH_EFFECT_UNKNOWN",
    }
    reconciliation_reasons: set[str] = set()
    for node in ast.walk(_tree(EXECUTOR)):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "ExecutionDirective":
            continue
        keywords = {item.arg: item.value for item in node.keywords if item.arg}
        code = keywords.get("code")
        reason = keywords.get("reason_code")
        if (
            isinstance(code, ast.Attribute)
            and code.attr == "RECONCILIATION_REQUIRED"
            and isinstance(reason, ast.Constant)
            and isinstance(reason.value, str)
        ):
            reconciliation_reasons.add(reason.value)

    assert required_reasons <= reconciliation_reasons


def test_executor_contains_no_retry_loop_or_recursive_cycle() -> None:
    tree = _tree(EXECUTOR)
    recursive_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute_cycle"
    ]

    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))
    assert recursive_calls == []


def test_executor_does_not_construct_plans_or_increment_versions() -> None:
    tree = _tree(EXECUTOR)
    plan_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Plan"
    ]
    version_increments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Add)
        and isinstance(node.left, ast.Attribute)
        and node.left.attr == "plan_version"
    ]

    assert plan_calls == []
    assert version_increments == []


def test_executor_constructs_no_routing_or_invocation_contract() -> None:
    forbidden_constructors = {
        "AgentInvocation",
        "DelegationEnvelope",
        "ToolCallRequest",
        "UseCaseRequest",
    }
    calls = {
        node.func.id
        for node in ast.walk(_tree(EXECUTOR))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert calls.isdisjoint(forbidden_constructors)


def test_step_spec_remains_immutable_declaration_without_runtime_status() -> None:
    params = StepSpec.__dataclass_params__

    assert params.frozen
    assert "status" not in {item.name for item in fields(StepSpec)}


def test_executor_does_not_anticipate_workflow_catalogue() -> None:
    strings = {
        node.value
        for path in _python_files(EXECUTION)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert all(not value.startswith("WF-") for value in strings)


def test_project_runtime_dependencies_remain_empty() -> None:
    import tomllib

    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["dependencies"] == ["openai>=3.5,<4"]
