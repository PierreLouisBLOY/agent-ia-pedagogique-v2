from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_ROOT = ROOT / "backend" / "agent_runtime" / "registry"
POLICY_ROOT = ROOT / "backend" / "agent_runtime" / "policy"
TOOLS = REGISTRY_ROOT / "tools.py"
TOOL_POLICY = POLICY_ROOT / "tool_call_policy.py"
B_FILES = (TOOLS, TOOL_POLICY)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _class_fields(path: Path, class_name: str) -> set[str]:
    class_node = next(
        node
        for node in _tree(path).body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return {
        item.target.id
        for item in class_node.body
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
    }


def test_tool_registry_is_distinct_from_the_single_capability_registry() -> None:
    capability_registry_definitions = [
        path
        for path in REGISTRY_ROOT.glob("*.py")
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == "CapabilityRegistry"
    ]
    tool_registry_definitions = [
        path
        for path in REGISTRY_ROOT.glob("*.py")
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == "ToolRegistry"
    ]

    assert capability_registry_definitions == [REGISTRY_ROOT / "capabilities.py"]
    assert tool_registry_definitions == [TOOLS]


def test_tool_descriptor_has_only_declarative_fields_and_does_not_duplicate_risk() -> None:
    fields = _class_fields(TOOLS, "ToolDescriptor")

    assert fields == {
        "tool_id",
        "canonical_name",
        "capability_id",
        "input_contract_id",
        "output_contract_id",
        "effect_class",
        "sandbox_profile_id",
        "idempotency_required",
        "timeout_ceiling",
    }
    assert fields.isdisjoint(
        {"risk", "handler", "callable", "provider", "credential", "connection"}
    )


def test_tool_call_policy_composes_the_canonical_capability_policy_only() -> None:
    source = TOOL_POLICY.read_text(encoding="utf-8")
    imported_names = {
        alias.name
        for node in ast.walk(_tree(TOOL_POLICY))
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert "CapabilityAuthorizationPolicy" in imported_names
    assert "self.capability_policy.evaluate" in source
    assert "PolicyDisposition.ALLOW" in source
    assert "AccessMatrix" not in imported_names
    assert "PermissionScopeEvaluator" not in imported_names


def test_b_defines_no_execution_router_handler_gate_or_sandbox_engine() -> None:
    forbidden_definitions = {
        "ToolRouter",
        "UseCaseRouter",
        "GateEngine",
        "Sandbox",
        "SandboxEngine",
        "ToolHandler",
        "ToolExecutor",
    }
    definitions = {
        node.name
        for path in B_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert definitions.isdisjoint(forbidden_definitions)


def test_b_imports_no_provider_network_filesystem_subprocess_or_dynamic_loader() -> None:
    forbidden_prefixes = (
        "backend.modules",
        "backend.adapters",
        "backend.infrastructure",
        "backend.providers",
        "http",
        "importlib",
        "os",
        "pathlib",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    )
    violations: list[str] = []

    for path in B_FILES:
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


def test_b_contains_no_eval_exec_reflection_or_plugin_discovery() -> None:
    forbidden_calls = {"eval", "exec", "getattr", "setattr", "__import__"}
    calls = {
        node.func.id
        for path in B_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    source = "\n".join(path.read_text(encoding="utf-8") for path in B_FILES)

    assert calls.isdisjoint(forbidden_calls)
    assert "entry_point" not in source.casefold()
    assert "plugin" not in source.casefold()


def test_baseline_registry_has_no_external_mutation_descriptor() -> None:
    tree = _tree(TOOLS)
    baseline_assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "BASELINE_TOOL_REGISTRY"
    )

    assert "ToolEffectClass.EXTERNAL_MUTATION" not in ast.unparse(
        baseline_assignment.value
    )


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["dependencies"] == ["openai>=3.5,<4"]
