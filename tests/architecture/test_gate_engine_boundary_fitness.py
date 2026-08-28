from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from backend.agent_runtime.contracts import ActorKind, GateDecision, GateRequest
from backend.agent_runtime.gates import (
    BASELINE_GATE_AUTHORITY_POLICY,
    GateDecisionSourcePort,
    GateEngine,
)

ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME = ROOT / "backend" / "agent_runtime"
GATES = AGENT_RUNTIME / "gates"
GATE_FILES = tuple(sorted(GATES.glob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _definitions(class_name: str) -> list[Path]:
    return [
        path
        for path in AGENT_RUNTIME.rglob("*.py")
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]


def test_gate_authority_types_and_canonical_contracts_have_single_definitions() -> None:
    assert len(_definitions(GateEngine.__name__)) == 1
    assert len(_definitions(GateDecisionSourcePort.__name__)) == 1
    assert len(_definitions(GateRequest.__name__)) == 1
    assert len(_definitions(GateDecision.__name__)) == 1


def test_gate_engine_reuses_canonical_contracts_and_user_only_baseline() -> None:
    source = (GATES / "engine.py").read_text(encoding="utf-8")

    assert "from backend.agent_runtime.contracts import" in source
    assert "GateRequest" in source
    assert "GateDecision" in source
    assert BASELINE_GATE_AUTHORITY_POLICY.allowed_actor_kinds == (ActorKind.USER,)
    assert "ActorKind.AGENT" in (GATES / "authority.py").read_text(encoding="utf-8")


def test_decision_source_is_protocol_only_with_one_receive_method() -> None:
    assert getattr(GateDecisionSourcePort, "_is_protocol", False)
    methods = {
        node.name
        for node in _tree(GATES / "ports.py").body
        if isinstance(node, ast.ClassDef) and node.name == "GateDecisionSourcePort"
        for node in node.body
        if isinstance(node, ast.FunctionDef)
    }

    assert methods == {"receive"}


def test_engine_has_one_source_call_and_no_polling_retry_or_background_loop() -> None:
    source = (GATES / "engine.py").read_text(encoding="utf-8")
    tree = _tree(GATES / "engine.py")
    definitions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    evaluate = next(
        child
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "GateEngine"
        for child in node.body
        if isinstance(child, ast.FunctionDef) and child.name == "evaluate"
    )

    assert source.count("self.decision_source.receive") == 1
    assert not any(
        isinstance(node, (ast.For, ast.While, ast.AsyncFor))
        for node in ast.walk(evaluate)
    )
    assert not any(name.casefold() in {"poll", "retry", "background"} for name in definitions)


def test_gate_package_imports_no_runtime_business_provider_or_io_boundary() -> None:
    forbidden_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
        "backend.providers",
        "backend.agent_runtime.application_routing",
        "backend.agent_runtime.runtime",
        "http",
        "importlib",
        "os",
        "pathlib",
        "requests",
        "socket",
        "sqlite3",
        "subprocess",
        "tempfile",
        "urllib",
    )
    violations: list[str] = []

    for path in GATE_FILES:
        for node in ast.walk(_tree(path)):
            modules: tuple[str, ...] = ()
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = (node.module,)
            violations.extend(
                f"{path.name}: {module}"
                for module in modules
                if module.startswith(forbidden_prefixes)
            )

    assert violations == []


def test_gate_package_has_no_io_dynamic_loading_or_deferred_runtime_types() -> None:
    forbidden_calls = {
        "__import__",
        "eval",
        "exec",
        "getattr",
        "open",
        "read_bytes",
        "read_text",
        "setattr",
        "write_bytes",
        "write_text",
    }
    calls = {
        node.func.id
        for path in GATE_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    definitions = {
        node.name
        for path in GATE_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert calls.isdisjoint(forbidden_calls)
    assert definitions.isdisjoint(
        {"PlanExecutor", "PreLaunchGuard", "PromotionPolicy", "Scheduler", "StepRunner"}
    )


def test_existing_routers_and_executor_do_not_depend_on_gate_engine() -> None:
    protected_files = (
        AGENT_RUNTIME / "application_routing" / "router.py",
        AGENT_RUNTIME / "tools" / "router.py",
        AGENT_RUNTIME / "runtime" / "execution" / "executor.py",
        AGENT_RUNTIME / "runtime" / "execution" / "prelaunch.py",
    )

    for path in protected_files:
        assert "agent_runtime.gates" not in path.read_text(encoding="utf-8")


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["dependencies"] == ["openai>=3.5,<4"]
