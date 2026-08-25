from __future__ import annotations

import ast
import inspect
import tomllib
from pathlib import Path

from backend.agent_runtime.agents.generation import GenerationPort
from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.registry import (
    BASELINE_AGENT_CAPABILITY_MATRIX,
    BASELINE_CAPABILITY_REGISTRY,
    AccessMode,
    CapabilityClass,
    CapabilityExecutionRoute,
    CapabilityRisk,
)
from backend.core_contracts.capability import CapabilityId

ROOT = Path(__file__).resolve().parents[2]
GENERATION = ROOT / "backend" / "agent_runtime" / "agents" / "generation"
MODEL = GENERATION / "generation_model.py"
PORTS = GENERATION / "generation_ports.py"
BOUNDARY_FILES = (MODEL, PORTS)


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


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


def _called_names() -> set[str]:
    return {
        node.func.id
        for path in _python_files(GENERATION)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _attribute_calls() -> set[str]:
    return {
        node.func.attr
        for path in _python_files(GENERATION)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def test_generation_package_exists_with_only_boundary_files() -> None:
    assert GENERATION.is_dir()
    assert {path.name for path in _python_files(GENERATION)} == {
        "__init__.py",
        "generation_agent.py",
        "generation_agent_model.py",
        "generation_coordination_model.py",
        "generation_coordinator.py",
        "generation_correction.py",
        "generation_correction_model.py",
        "generation_model.py",
        "generation_ports.py",
    }


def test_generation_boundary_has_no_runtime_or_orchestration_imports() -> None:
    imports = {module for path in _python_files(GENERATION) for module in _imports(path)}
    assert all(not module.startswith("backend.agent_runtime.runtime") for module in imports)
    assert all(
        not module.startswith("backend.agent_runtime.orchestration") for module in imports
    )


def test_generation_boundary_has_no_modules_adapters_or_infrastructure_imports() -> None:
    forbidden = ("backend.modules", "backend.adapters", "backend.infrastructure")
    imports = {module for path in _python_files(GENERATION) for module in _imports(path)}
    assert all(not module.startswith(forbidden) for module in imports)


def test_generation_boundary_has_no_provider_network_sql_or_filesystem_imports() -> None:
    forbidden_roots = {
        "aiohttp",
        "anthropic",
        "asyncio",
        "django",
        "fastapi",
        "google",
        "httpx",
        "langchain",
        "langgraph",
        "multiprocessing",
        "openai",
        "pathlib",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "threading",
        "urllib",
    }
    imported_roots = {
        module.split(".")[0]
        for path in _python_files(GENERATION)
        for module in _imports(path)
    }
    assert imported_roots.isdisjoint(forbidden_roots)


def test_generation_boundary_has_no_io_or_network_attribute_calls() -> None:
    attribute_calls = {
        node.func.attr
        for path in BOUNDARY_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert attribute_calls.isdisjoint(
        {
            "connect",
            "execute",
            "get",
            "open",
            "post",
            "read_bytes",
            "read_text",
            "request",
            "urlopen",
            "write_bytes",
            "write_text",
        }
    )


def test_generation_boundary_has_no_while_retry_backoff_or_sleep() -> None:
    assert not any(
        isinstance(node, ast.While)
        for path in _python_files(GENERATION)
        for node in ast.walk(_tree(path))
    )
    assert _called_names().isdisjoint({"backoff", "retry", "sleep"})


def test_generation_boundary_constructs_no_agent_or_canonical_output_contract() -> None:
    called_names = {
        node.func.id
        for path in BOUNDARY_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called_names.isdisjoint(
        {
            "CorrectionResult",
            "EvidenceSet",
            "ProductionCandidate",
        }
    )
    imports = {module for path in BOUNDARY_FILES for module in _imports(path)}
    assert all("production_candidate" not in module for module in imports)
    assert all("correction_result" not in module for module in imports)


def test_generation_boundary_constructs_no_gate_permission_or_runtime_authority() -> None:
    assert _called_names().isdisjoint(
        {
            "AgentInvocation",
            "CapabilityId",
            "GateDecision",
            "PermissionScope",
            "PlanExecutor",
            "StepRunner",
        }
    )


def test_generation_boundary_has_no_router_dispatcher_handler_or_store() -> None:
    forbidden = ("router", "dispatcher", "handler", "store")
    class_names = {
        node.name.casefold()
        for path in _python_files(GENERATION)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert all(not any(item in name for item in forbidden) for name in class_names)


def test_generation_boundary_has_no_validate_promote_search_or_tool_side_effect() -> None:
    functions = {
        node.name
        for path in _python_files(GENERATION)
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert functions.isdisjoint(
        {"promote", "review", "search", "tool_call", "validate"}
    )
    assert _attribute_calls().isdisjoint(
        {"promote", "review", "search", "tool_call", "validate"}
    )


def test_generation_port_is_the_only_runtime_checkable_protocol_operation() -> None:
    assert getattr(GenerationPort, "_is_protocol", False)
    assert getattr(GenerationPort, "_is_runtime_protocol", False)
    assert tuple(inspect.signature(GenerationPort.generate).parameters) == (
        "self",
        "request",
    )
    public_methods = {
        name
        for name, value in GenerationPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert public_methods == {"generate"}


def test_generation_port_has_no_production_implementation() -> None:
    classes = {
        node.name: tuple(
            base.id for base in node.bases if isinstance(base, ast.Name)
        )
        for path in _python_files(GENERATION)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert classes["GenerationPort"] == ("Protocol",)
    assert all(
        "GenerationPort" not in bases
        for name, bases in classes.items()
        if name != "GenerationPort"
    )


def test_generation_boundary_contains_no_provider_model_endpoint_or_prompt_template() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in _python_files(GENERATION)
    )
    assert all(
        token not in source
        for token in (
            "api_key",
            "endpoint_url",
            "gpt-",
            "claude-",
            "gemini-",
            "prompt_template",
            "provider_response",
        )
    )


def test_ag03_registry_capabilities_remain_exact() -> None:
    descriptors = BASELINE_CAPABILITY_REGISTRY.owned_by(AgentId.AG_03)
    assert tuple(item.capability_id.value for item in descriptors) == (
        "CAP-G01",
        "CAP-G02",
        "CAP-G03",
    )
    assert tuple(item.canonical_name for item in descriptors) == (
        "generate_production",
        "transform_production",
        "correct_production",
    )
    assert all(item.capability_class is CapabilityClass.GENERATE_TRANSFORM for item in descriptors)
    assert all(item.execution_route is CapabilityExecutionRoute.AGENT for item in descriptors)
    assert all(item.risk is CapabilityRisk.R1 for item in descriptors)


def test_ag03_access_matrix_allows_only_generation_specialist_capabilities() -> None:
    for code in ("CAP-G01", "CAP-G02", "CAP-G03"):
        assert (
            BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(
                AgentId.AG_03,
                CapabilityId(code),
            ).mode
            is AccessMode.ALLOW
        )

    forbidden_codes = (
        "CAP-E01",
        "CAP-E02",
        "CAP-E03",
        "CAP-V01",
        "CAP-V02",
        "CAP-A01",
        "CAP-A02",
        "CAP-A03",
        "CAP-O01",
        "CAP-O02",
        "CAP-O03",
        "CAP-O04",
        "CAP-O05",
        "CAP-O06",
    )
    assert all(
        BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(
            AgentId.AG_03,
            CapabilityId(code),
        ).mode
        is AccessMode.DENY
        for code in forbidden_codes
    )


def test_generation_models_do_not_import_canonical_request_mapping_targets() -> None:
    imported = set(_imports(MODEL)) | set(_imports(PORTS))
    assert all("production_request" not in module for module in imported)
    assert all("correction_request" not in module for module in imported)
    assert all("evidence" not in module for module in imported)


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == []
