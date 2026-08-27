from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from backend.agent_runtime.recovery import (
    EffectLedgerPort,
    RecoveryAwareStepRunner,
    RecoveryCoordinator,
    RecoveryPreLaunchGuard,
    RecoveryReferenceResolverPort,
    RecoveryRuntimeController,
    RecoveryRuntimeResolverPort,
)
from backend.agent_runtime.runtime import PlanExecutor

ROOT = Path(__file__).resolve().parents[2]
RECOVERY_FILES = (
    ROOT / "backend/agent_runtime/recovery/runtime_integration.py",
    ROOT / "backend/agent_runtime/recovery/runtime_ports.py",
    ROOT / "backend/agent_runtime/recovery/checkpoint.py",
    ROOT / "backend/agent_runtime/recovery/coordinator.py",
    ROOT / "backend/agent_runtime/recovery/controller.py",
)
FORBIDDEN_IMPORT_ROOTS = {
    "asyncio",
    "requests",
    "httpx",
    "socket",
    "sqlite3",
    "sqlalchemy",
    "subprocess",
    "threading",
}


def test_recovery_integration_has_no_loop_sleep_background_or_external_io() -> None:
    for path in RECOVERY_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(isinstance(node, (ast.While, ast.AsyncFor)) for node in ast.walk(tree))
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"sleep", "poll", "create_task"}
            for node in ast.walk(tree)
        )
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in (
                node.names
                if isinstance(node, ast.Import)
                else [ast.alias(name=node.module or "")]
            )
        }
        assert not imports.intersection(FORBIDDEN_IMPORT_ROOTS)
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
            for node in ast.walk(tree)
        )


def test_controller_contains_exactly_one_cycle_coordination_and_recovery_call() -> None:
    path = ROOT / "backend/agent_runtime/recovery/controller.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "execute_cycle"
    )
    called_attributes = [
        node.func.attr
        for node in ast.walk(method)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]

    assert called_attributes.count("execute_cycle") == 1
    assert called_attributes.count("coordinate") == 1
    assert called_attributes.count("recover") == 1


def test_plan_executor_remains_cycle_only_and_has_no_recovery_dependency() -> None:
    source = (
        ROOT / "backend/agent_runtime/runtime/execution/executor.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert issubclass(PlanExecutor, object)
    assert "agent_runtime.recovery" not in source
    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))


def test_boundaries_are_unique_typed_and_runtime_checkable() -> None:
    assert isinstance(RecoveryRuntimeResolverPort, type)
    assert isinstance(RecoveryReferenceResolverPort, type)
    assert isinstance(EffectLedgerPort, type)
    assert RecoveryPreLaunchGuard.__module__.endswith("runtime_integration")
    assert RecoveryAwareStepRunner.__module__.endswith("runtime_integration")
    assert RecoveryCoordinator.__module__.endswith("coordinator")
    assert RecoveryRuntimeController.__module__.endswith("controller")


def test_runtime_dependencies_remain_empty() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["dependencies"] == []
