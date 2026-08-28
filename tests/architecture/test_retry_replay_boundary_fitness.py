from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECOVERY = ROOT / "backend" / "agent_runtime" / "recovery"
E_BOUNDARY = (
    RECOVERY / "backoff.py",
    RECOVERY / "replay.py",
    RECOVERY / "retry.py",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_e_boundary_is_pure_and_has_no_io_or_scheduling_dependencies() -> None:
    forbidden_roots = {
        "asyncio",
        "httpx",
        "os",
        "pathlib",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "threading",
        "time",
        "urllib",
    }
    for path in E_BOUNDARY:
        imports = _imported_modules(path)
        assert {module.split(".")[0] for module in imports}.isdisjoint(
            forbidden_roots
        )
        tree = _tree(path)
        assert not any(
            isinstance(node, (ast.While, ast.AsyncFor, ast.AsyncFunctionDef))
            for node in ast.walk(tree)
        )


def test_e_does_not_define_execution_or_circuit_components() -> None:
    forbidden_classes = {
        "CircuitBreaker",
        "CircuitBreakerPolicy",
        "RecoveryCoordinator",
        "ReplayExecutor",
        "RetryExecutor",
    }
    classes = {
        node.name
        for path in E_BOUNDARY
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert classes.isdisjoint(forbidden_classes)


def test_replay_and_retry_results_require_future_circuit_check() -> None:
    for path, class_name in (
        (RECOVERY / "replay.py", "ReplayGuardDecision"),
        (RECOVERY / "retry.py", "RetryDecision"),
    ):
        class_node = next(
            node
            for node in _tree(path).body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )
        source = ast.get_source_segment(
            path.read_text(encoding="utf-8"),
            class_node,
        )
        assert source is not None
        assert "requires_circuit_check" in source
        assert "default=True" in source
        assert "init=False" in source


def test_e_does_not_modify_runtime_executor_or_add_runtime_dependency() -> None:
    forbidden_imports = {
        "backend.agent_runtime.gates",
        "backend.agent_runtime.runtime.execution",
        "backend.agent_runtime.tools",
    }
    for path in E_BOUNDARY:
        assert _imported_modules(path).isdisjoint(forbidden_imports)
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["dependencies"] == ["openai>=3.5,<4"]


def test_backoff_contains_no_waiting_or_retry_loop_calls() -> None:
    tree = _tree(RECOVERY / "backoff.py")
    forbidden_calls = {"sleep", "wait", "retry", "replay", "create_task"}
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called.isdisjoint(forbidden_calls)
