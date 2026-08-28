from __future__ import annotations

import ast
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.application_routing import (
    ApplicationInboundPort,
    UseCaseDescriptor,
    UseCaseInboundBinding,
    UseCaseRegistry,
    UseCaseRouter,
)

ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME = ROOT / "backend" / "agent_runtime"
APPLICATION_ROUTING = AGENT_RUNTIME / "application_routing"
ROUTING_FILES = tuple(sorted(APPLICATION_ROUTING.glob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _definitions(class_name: str) -> list[Path]:
    return [
        path
        for path in AGENT_RUNTIME.rglob("*.py")
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]


def test_use_case_routing_authority_types_have_single_definitions() -> None:
    assert len(_definitions(UseCaseRegistry.__name__)) == 1
    assert len(_definitions(UseCaseRouter.__name__)) == 1
    assert len(_definitions(ApplicationInboundPort.__name__)) == 1


def test_descriptor_has_only_metadata_and_binding_keeps_port_separate() -> None:
    assert {field.name for field in fields(UseCaseDescriptor)} == {
        "use_case_id",
        "canonical_name",
        "capability_id",
        "request_contract_id",
        "result_contract_id",
        "idempotency_required",
    }
    assert {field.name for field in fields(UseCaseInboundBinding)} == {
        "use_case_id",
        "inbound",
    }
    assert {field.name for field in fields(UseCaseDescriptor)}.isdisjoint(
        {"handler", "callable", "handler_path", "import_path", "provider", "owner"}
    )


def test_application_inbound_port_is_provider_neutral_with_one_method() -> None:
    assert getattr(ApplicationInboundPort, "_is_protocol", False)
    methods = {
        node.name
        for node in _tree(APPLICATION_ROUTING / "ports.py").body
        if isinstance(node, ast.ClassDef) and node.name == "ApplicationInboundPort"
        for node in node.body
        if isinstance(node, ast.FunctionDef)
    }

    assert methods == {"invoke"}


def test_router_preserves_policy_request_binding_inbound_validation_order() -> None:
    source = (APPLICATION_ROUTING / "router.py").read_text(encoding="utf-8")

    policy = source.index("self.capability_policy.evaluate")
    request_only = source.index("if not _is_routable_application_request")
    binding = source.index("self.inbound_bindings.get")
    inbound = source.index("inbound.invoke")
    validation = source.index("return _validate_result")

    assert policy < request_only < binding < inbound < validation
    assert source.count("inbound.invoke") == 1


def test_routing_package_has_no_business_provider_io_or_dynamic_loader_imports() -> None:
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

    for path in ROUTING_FILES:
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


def test_routing_package_has_no_io_reflection_plugins_gates_runner_or_retry() -> None:
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
        for path in ROUTING_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    definitions = {
        node.name
        for path in ROUTING_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    source = "\n".join(path.read_text(encoding="utf-8") for path in ROUTING_FILES)

    assert calls.isdisjoint(forbidden_calls)
    assert definitions.isdisjoint({"GateEngine", "PlanExecutor", "Scheduler", "StepRunner"})
    assert "entry_point" not in source.casefold()
    assert "plugin" not in source.casefold()
    assert not any(name.casefold() == "retry" for name in definitions | calls)


def test_existing_tool_and_application_modules_do_not_reverse_dependency() -> None:
    tool_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (AGENT_RUNTIME / "tools").glob("*.py")
    )
    module_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "backend" / "modules").rglob("*.py")
    )

    assert "application_routing" not in tool_source
    assert "agent_runtime.application_routing" not in module_source


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["dependencies"] == ["openai>=3.5,<4"]
