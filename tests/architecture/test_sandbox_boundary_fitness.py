from __future__ import annotations

import ast
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.registry import ToolRegistry
from backend.agent_runtime.sandbox import (
    SandboxFilesystemPort,
    SandboxPolicy,
    SandboxProfile,
    SandboxProfileRegistry,
)

ROOT = Path(__file__).resolve().parents[2]
SANDBOX = ROOT / "backend" / "agent_runtime" / "sandbox"
SANDBOX_FILES = tuple(sorted(SANDBOX.glob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_sandbox_defines_distinct_registry_policy_and_filesystem_port() -> None:
    assert SandboxProfileRegistry is not ToolRegistry
    assert SandboxPolicy is not SandboxProfileRegistry
    assert getattr(SandboxFilesystemPort, "_is_protocol", False)


def test_sandbox_profile_has_no_os_root_handler_or_authority_fields() -> None:
    profile_fields = {field.name for field in fields(SandboxProfile)}

    assert profile_fields.isdisjoint(
        {
            "absolute_path",
            "root_path",
            "handler",
            "callable",
            "tool_id",
            "capability_id",
            "permission_scope",
            "gate_approval",
            "provider",
        }
    )


def test_sandbox_imports_no_adapter_infrastructure_provider_network_or_os_io() -> None:
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

    for path in SANDBOX_FILES:
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


def test_sandbox_contains_no_io_execution_dynamic_import_or_reflection_calls() -> None:
    forbidden_calls = {
        "__import__",
        "chmod",
        "eval",
        "exec",
        "getattr",
        "open",
        "read",
        "read_bytes",
        "read_text",
        "setattr",
        "write",
        "write_bytes",
        "write_text",
    }
    calls = {
        node.func.id
        for path in SANDBOX_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert calls.isdisjoint(forbidden_calls)


def test_sandbox_defines_no_router_gate_handler_or_adapter_implementation() -> None:
    forbidden_definitions = {
        "GateEngine",
        "SandboxFilesystemAdapter",
        "SandboxHandler",
        "ToolHandler",
        "ToolRouter",
        "UseCaseRouter",
    }
    definitions = {
        node.name
        for path in SANDBOX_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert definitions.isdisjoint(forbidden_definitions)


def test_sandbox_policy_does_not_own_tool_or_permission_authorization() -> None:
    policy_source = (SANDBOX / "policy.py").read_text(encoding="utf-8")
    imported_names = {
        alias.name
        for node in ast.walk(_tree(SANDBOX / "policy.py"))
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert "ToolCallPolicy" not in imported_names
    assert "CapabilityAuthorizationPolicy" not in imported_names
    assert "PermissionScopeEvaluator" not in imported_names
    assert "permission_scope" not in policy_source


def test_filesystem_port_exposes_only_resolve_and_inspect() -> None:
    methods = {
        node.name
        for node in _tree(SANDBOX / "ports.py").body
        if isinstance(node, ast.ClassDef) and node.name == "SandboxFilesystemPort"
        for node in node.body
        if isinstance(node, ast.FunctionDef)
    }

    assert methods == {"resolve", "inspect"}


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["dependencies"] == []
