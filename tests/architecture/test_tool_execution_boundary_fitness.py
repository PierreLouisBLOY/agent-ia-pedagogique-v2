from __future__ import annotations

import ast
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.policy import ToolCallPolicy
from backend.agent_runtime.registry import ToolDescriptor, ToolRegistry
from backend.agent_runtime.sandbox import SandboxPolicy, SandboxProfileRegistry
from backend.agent_runtime.tools import (
    ToolExecutorBinding,
    ToolExecutorPort,
    ToolRouter,
)

ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME = ROOT / "backend" / "agent_runtime"
TOOLS = AGENT_RUNTIME / "tools"
TOOL_FILES = tuple(sorted(TOOLS.glob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _definitions(class_name: str) -> list[Path]:
    return [
        path
        for path in AGENT_RUNTIME.rglob("*.py")
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]


def test_authority_registries_and_policies_remain_singletons_by_type() -> None:
    assert len(_definitions(ToolRegistry.__name__)) == 1
    assert len(_definitions(ToolCallPolicy.__name__)) == 1
    assert len(_definitions(SandboxProfileRegistry.__name__)) == 1
    assert len(_definitions(SandboxPolicy.__name__)) == 1
    assert len(_definitions(ToolRouter.__name__)) == 1


def test_executor_binding_is_distinct_from_tool_metadata() -> None:
    descriptor_fields = {field.name for field in fields(ToolDescriptor)}
    binding_fields = {field.name for field in fields(ToolExecutorBinding)}

    assert binding_fields == {"tool_id", "executor"}
    assert descriptor_fields.isdisjoint(
        {"executor", "handler", "callable", "provider", "class_path"}
    )


def test_executor_port_is_provider_neutral_and_has_one_execute_method() -> None:
    assert getattr(ToolExecutorPort, "_is_protocol", False)
    methods = {
        node.name
        for node in _tree(TOOLS / "ports.py").body
        if isinstance(node, ast.ClassDef) and node.name == "ToolExecutorPort"
        for node in node.body
        if isinstance(node, ast.FunctionDef)
    }

    assert methods == {"execute"}


def test_router_source_preserves_policy_sandbox_binding_execution_order() -> None:
    source = (TOOLS / "router.py").read_text(encoding="utf-8")

    tool_policy = source.index("self.tool_call_policy.evaluate")
    tool_allow = source.index("ToolCallDisposition.ALLOW")
    sandbox_preflight = source.index("self._sandbox_preflight")
    binding = source.index("self.executor_bindings.get")
    execution = source.index("executor.execute")
    post_validation = source.index("self._post_validate_outputs")

    assert tool_policy < tool_allow < sandbox_preflight < binding < execution
    assert execution < post_validation
    assert source.count("executor.execute") == 1


def test_tools_import_no_provider_network_os_subprocess_or_dynamic_loader() -> None:
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
        "shutil",
        "socket",
        "subprocess",
        "tempfile",
        "urllib",
    )
    violations: list[str] = []

    for path in TOOL_FILES:
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


def test_tools_contain_no_shell_io_dynamic_import_plugin_or_reflection() -> None:
    forbidden_calls = {
        "__import__",
        "chmod",
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
        for path in TOOL_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    source = "\n".join(path.read_text(encoding="utf-8") for path in TOOL_FILES)

    assert calls.isdisjoint(forbidden_calls)
    assert "entry_point" not in source.casefold()
    assert "plugin" not in source.casefold()


def test_d_defines_no_deferred_router_gate_scheduler_or_runtime_runner() -> None:
    forbidden_definitions = {
        "GateEngine",
        "PlanExecutor",
        "Scheduler",
        "StepRunner",
        "UseCaseRouter",
    }
    definitions = {
        node.name
        for path in TOOL_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert definitions.isdisjoint(forbidden_definitions)
    imported_modules = {
        node.module
        for path in TOOL_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert all("agent_runtime.recovery" not in module for module in imported_modules)


def test_router_does_not_import_permission_or_gate_engines() -> None:
    imported_names = {
        alias.name
        for node in ast.walk(_tree(TOOLS / "router.py"))
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert "AccessMatrix" not in imported_names
    assert "CapabilityAuthorizationPolicy" not in imported_names
    assert "PermissionScopeEvaluator" not in imported_names
    assert "GateEngine" not in imported_names
    assert "PlanExecutor" not in imported_names


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["dependencies"] == ["openai>=3.5,<4"]
