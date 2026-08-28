from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from backend.agent_runtime.application_routing import UseCaseRegistry, UseCaseRouter
from backend.agent_runtime.gates import GateEngine
from backend.agent_runtime.policy import CapabilityAuthorizationPolicy, ToolCallPolicy
from backend.agent_runtime.registry import CapabilityRegistry, ToolRegistry
from backend.agent_runtime.runtime import PlanExecutor
from backend.agent_runtime.runtime.routing import (
    RoutingPreLaunchGuard,
    RoutingStepRunner,
    RuntimeRoutingResolverPort,
)
from backend.agent_runtime.sandbox import SandboxPolicy, SandboxProfileRegistry
from backend.agent_runtime.tools import ToolRouter

ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME = ROOT / "backend" / "agent_runtime"
ROUTING = AGENT_RUNTIME / "runtime" / "routing"
ROUTING_FILES = tuple(sorted(ROUTING.glob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _definitions(class_name: str) -> list[Path]:
    return [
        path
        for path in AGENT_RUNTIME.rglob("*.py")
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]


def test_b_to_g_authority_types_remain_single_definitions() -> None:
    for authority_type in (
        CapabilityRegistry,
        ToolRegistry,
        SandboxProfileRegistry,
        UseCaseRegistry,
        CapabilityAuthorizationPolicy,
        ToolCallPolicy,
        SandboxPolicy,
        ToolRouter,
        UseCaseRouter,
        GateEngine,
        PlanExecutor,
        RoutingPreLaunchGuard,
        RoutingStepRunner,
        RuntimeRoutingResolverPort,
    ):
        assert len(_definitions(authority_type.__name__)) == 1


def test_resolver_is_typed_and_has_no_generic_resolve_method() -> None:
    assert getattr(RuntimeRoutingResolverPort, "_is_protocol", False)
    protocol = next(
        node
        for node in _tree(ROUTING / "ports.py").body
        if isinstance(node, ast.ClassDef)
        and node.name == "RuntimeRoutingResolverPort"
    )
    methods = {
        node.name for node in protocol.body if isinstance(node, ast.FunctionDef)
    }

    assert methods == {
        "resolve_agent_input",
        "resolve_gate_input",
        "resolve_tool_input",
        "resolve_use_case_input",
    }
    assert "resolve" not in methods


def test_routing_has_no_io_provider_network_shell_or_dynamic_loading() -> None:
    forbidden_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
        "backend.providers",
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
    imports: list[str] = []
    calls: set[str] = set()
    for path in ROUTING_FILES:
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.append(node.module)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.add(node.func.id)

    assert not any(module.startswith(forbidden_prefixes) for module in imports)
    assert calls.isdisjoint(forbidden_calls)


def test_routing_contains_no_second_engine_retry_polling_or_handler_factory() -> None:
    definitions = {
        node.name
        for path in ROUTING_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    source = "\n".join(path.read_text(encoding="utf-8") for path in ROUTING_FILES)

    assert definitions.isdisjoint(
        {
            "DeterministicScheduler",
            "GenericRouter",
            "HandlerFactory",
            "PlanExecutor",
            "PluginRegistry",
        }
    )
    assert "while " not in source
    assert "poll(" not in source.casefold()
    assert "import_path" not in source
    assert "handler_path" not in source


def test_agent_permission_operation_mapping_is_closed_and_canonical() -> None:
    source = (ROUTING / "agent_router.py").read_text(encoding="utf-8")

    assert '"CAP-E03": PermissionOperation.READ' in source
    assert '"CAP-G01": PermissionOperation.CREATE' in source
    assert '"CAP-G02": PermissionOperation.TRANSFORM' in source
    assert '"CAP-V02": PermissionOperation.REVIEW' in source


def test_plan_executor_remains_unchanged_by_g() -> None:
    executor_source = AGENT_RUNTIME / "runtime" / "execution" / "executor.py"

    assert "runtime.routing" not in executor_source.read_text(encoding="utf-8")


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["dependencies"] == ["openai>=3.5,<4"]
