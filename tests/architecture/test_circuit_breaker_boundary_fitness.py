from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
RECOVERY = BACKEND / "agent_runtime" / "recovery"
F_FILES = (
    RECOVERY / "circuit_breaker.py",
    RECOVERY / "circuit_breaker_ports.py",
    RECOVERY / "circuit_breaker_engine.py",
)


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _defined_classes(root: Path, class_name: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _python_files(root)
        if any(
            isinstance(node, ast.ClassDef) and node.name == class_name
            for node in ast.walk(_tree(path))
        )
    )


def _imports(paths: tuple[Path, ...]) -> set[str]:
    modules: set[str] = set()
    for path in paths:
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
    return modules


def test_circuit_status_policy_port_and_engine_are_unique() -> None:
    expected = {
        "CircuitBreakerStatus": RECOVERY / "circuit_breaker.py",
        "CircuitBreakerPolicy": RECOVERY / "circuit_breaker.py",
        "CircuitBreakerStorePort": RECOVERY / "circuit_breaker_ports.py",
        "CircuitBreakerEngine": RECOVERY / "circuit_breaker_engine.py",
    }
    for class_name, path in expected.items():
        assert _defined_classes(BACKEND, class_name) == (path,)


def test_store_is_protocol_only_and_no_production_memory_store_exists() -> None:
    ports = _tree(RECOVERY / "circuit_breaker_ports.py")
    protocols = {
        node.name
        for node in ports.body
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(base, ast.Name) and base.id == "Protocol"
            for base in node.bases
        )
    }
    assert protocols == {"CircuitBreakerStorePort"}
    source = "\n".join(path.read_text(encoding="utf-8") for path in F_FILES)
    assert "InMemory" not in source


def test_f_has_no_io_execution_authority_or_router_dependencies() -> None:
    imports = _imports(F_FILES)
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
    assert {module.split(".")[0] for module in imports}.isdisjoint(forbidden_roots)
    forbidden_fragments = {
        "agent_runtime.application_routing",
        "agent_runtime.gates",
        "agent_runtime.orchestration",
        "agent_runtime.runtime.execution",
        "agent_runtime.runtime.routing",
        "agent_runtime.tools",
    }
    assert all(
        fragment not in module
        for fragment in forbidden_fragments
        for module in imports
    )


def test_f_contains_no_loop_retry_replay_sleep_or_dependency_call() -> None:
    forbidden_calls = {
        "create_task",
        "execute",
        "invoke",
        "poll",
        "replay",
        "retry",
        "route",
        "sleep",
    }
    for path in F_FILES:
        tree = _tree(path)
        assert not any(
            isinstance(node, (ast.While, ast.AsyncFor, ast.AsyncFunctionDef))
            for node in ast.walk(tree)
        )
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        called_attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert (called_names | called_attributes).isdisjoint(forbidden_calls)


def test_key_is_exact_binding_not_capability_global() -> None:
    tree = _tree(RECOVERY / "circuit_breaker.py")
    key = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "CircuitBreakerKey"
    )
    annotations = {
        node.target.id
        for node in key.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    }
    assert annotations == {"execution_route", "target_id", "binding_id"}
    assert "capability_id" not in annotations


def test_f_exposes_no_manual_reset_or_force_api() -> None:
    methods = {
        node.name
        for path in F_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert methods.isdisjoint(
        {"force_close", "force_open", "manual_reset", "reset", "reset_circuit"}
    )


def test_project_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["dependencies"] == []
