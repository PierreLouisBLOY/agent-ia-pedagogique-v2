from __future__ import annotations

import ast
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.orchestration import OrchestrationCoordinator

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
AGENT_RUNTIME = BACKEND / "agent_runtime"
ORCHESTRATION = AGENT_RUNTIME / "orchestration"
COORDINATION = ORCHESTRATION / "coordination"
COORDINATOR = COORDINATION / "coordinator.py"
COMPLETION = COORDINATION / "completion.py"
RUNTIME = AGENT_RUNTIME / "runtime"


def _python_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> tuple[str, ...]:
    modules: list[str] = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    return tuple(modules)


def _called_names(root: Path) -> set[str]:
    return {
        node.func.id
        for path in _python_files(root)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _function(path: Path, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_coordination_package_is_confined_to_orchestration() -> None:
    assert COORDINATION.is_dir()
    assert {path.name for path in COORDINATION.glob("*.py")} == {
        "__init__.py",
        "completion.py",
        "coordinator.py",
        "model.py",
    }
    expected_names = {
        "CompletionDisposition",
        "CoordinationAction",
        "CoordinationDecision",
        "CoordinationError",
        "CoordinationErrorCode",
        "OrchestrationCoordinator",
        "WorkflowCompletionDecision",
        "WorkflowCompletionEvaluator",
    }
    definitions = {
        node.name: path.parent.relative_to(ROOT).as_posix()
        for path in _python_files(BACKEND)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name in expected_names
    }
    assert definitions == {
        name: "backend/agent_runtime/orchestration/coordination"
        for name in expected_names
    }


def test_runtime_does_not_depend_on_orchestration_coordination() -> None:
    imports = {module for path in _python_files(RUNTIME) for module in _imports(path)}
    assert all("orchestration.coordination" not in module for module in imports)


def test_coordination_has_no_provider_transport_persistence_or_concurrency_import() -> None:
    forbidden_roots = {
        "aiohttp",
        "asyncio",
        "django",
        "fastapi",
        "flask",
        "httpx",
        "multiprocessing",
        "openai",
        "requests",
        "sqlalchemy",
        "sqlite3",
        "threading",
    }
    forbidden_backend_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
    )
    imported = {
        module for path in _python_files(COORDINATION) for module in _imports(path)
    }
    assert not {module.split(".")[0] for module in imported} & forbidden_roots
    assert all(not module.startswith(forbidden_backend_prefixes) for module in imported)


def test_coordination_contains_no_llm_rag_http_orm_or_sql_vocabulary() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(COORDINATION)
    ).casefold()
    assert all(
        forbidden not in source
        for forbidden in (
            "provider",
            "llm",
            "rag",
            "http",
            "sql",
            "orm",
            "sqlite3",
        )
    )


def test_coordinator_takes_no_executor_runner_guard_router_or_provider() -> None:
    field_names = {field.name for field in fields(OrchestrationCoordinator)}
    source = COORDINATOR.read_text(encoding="utf-8")
    assert field_names == {"completion_evaluator", "revision_engine"}
    assert all(
        forbidden not in source
        for forbidden in (
            "PlanExecutor",
            "StepRunner",
            "PreLaunchGuard",
            "GateEngine",
            "router",
            "provider",
        )
    )


def test_coordination_never_calls_execute_cycle_or_constructs_invocations() -> None:
    attribute_calls = {
        node.func.attr
        for path in _python_files(COORDINATION)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    calls = _called_names(COORDINATION)
    assert "execute_cycle" not in attribute_calls
    assert calls.isdisjoint(
        {
            "AgentInvocation",
            "DelegationEnvelope",
            "ToolCallRequest",
            "UseCaseRequest",
        }
    )


def test_coordination_constructs_or_consumes_no_gate_contract() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(COORDINATION)
    )
    assert "GateDecision" not in source
    assert "GateEngine" not in source


def test_coordination_evaluates_no_permission_or_access_matrix() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(COORDINATION)
    )
    assert "PermissionScope" not in source
    assert "AccessMatrix" not in source


def test_coordination_has_no_retry_loop_backoff_sleep_or_parallelism() -> None:
    trees = [_tree(path) for path in _python_files(COORDINATION)]
    called_names = _called_names(COORDINATION)
    imported_roots = {
        module.split(".")[0]
        for path in _python_files(COORDINATION)
        for module in _imports(path)
    }
    assert not any(
        isinstance(node, ast.While) for tree in trees for node in ast.walk(tree)
    )
    coordinator_calls = {
        node.func.attr
        for node in ast.walk(_function(COORDINATOR, "coordinate"))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "coordinate" not in coordinator_calls
    assert called_names.isdisjoint({"sleep", "backoff"})
    assert imported_roots.isdisjoint(
        {"asyncio", "threading", "multiprocessing"}
    )


def test_completion_evaluator_is_protocol_only_without_production_implementation() -> None:
    classes = {
        node.name: tuple(
            base.id for base in node.bases if isinstance(base, ast.Name)
        )
        for path in _python_files(COORDINATION)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert classes["WorkflowCompletionEvaluator"] == ("Protocol",)
    assert not any(
        "WorkflowCompletionEvaluator" in bases
        for name, bases in classes.items()
        if name != "WorkflowCompletionEvaluator"
    )
    assert {path.name for path in COORDINATION.glob("*evaluator*.py")} == set()


def test_apply_replan_calls_revision_engine_once_and_returns_directly() -> None:
    function = _function(COORDINATOR, "apply_replan")
    revise_calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "revise"
    ]
    returns = [node for node in ast.walk(function) if isinstance(node, ast.Return)]
    assert len(revise_calls) == 1
    assert len(returns) == 1 and returns[0].value is revise_calls[0]
    assert not any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(function))


def test_apply_replan_does_not_select_compile_or_construct_replacement() -> None:
    function = _function(COORDINATOR, "apply_replan")
    calls = {
        node.func.attr
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    name_calls = {
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert calls.isdisjoint({"select", "compile"})
    assert name_calls.isdisjoint({"WorkflowSelector", "PlanCompiler", "Plan"})


def test_coordination_does_not_import_or_mutate_agent_runtime_policy() -> None:
    imported = {
        module for path in _python_files(COORDINATION) for module in _imports(path)
    }
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(COORDINATION)
    )
    assert all("agent_runtime.policy" not in module for module in imported)
    assert "AgentRuntimePolicy" not in source


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == ["openai>=3.5,<4"]
