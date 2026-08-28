from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "backend" / "agent_runtime" / "registry"
POLICY = ROOT / "backend" / "agent_runtime" / "policy"


def _python_files() -> list[Path]:
    return sorted((*REGISTRY.glob("*.py"), *POLICY.glob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_registry_and_policy_imports_stay_inside_allowed_boundaries() -> None:
    forbidden_prefixes = (
        "backend.modules",
        "backend.adapters",
        "backend.infrastructure",
        "backend.providers",
    )
    violations: list[str] = []

    for path in _python_files():
        for node in ast.walk(_tree(path)):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = [node.module]
            violations.extend(
                f"{path.relative_to(ROOT).as_posix()}: {module}"
                for module in modules
                if module.startswith(forbidden_prefixes) or ".provider" in module.casefold()
            )

    assert violations == []


def test_registry_descriptors_store_no_concrete_execution_binding() -> None:
    forbidden_fields = {
        "provider",
        "provider_id",
        "tool",
        "tool_id",
        "handler",
        "use_case",
        "use_case_handler",
    }
    descriptor_fields: dict[str, set[str]] = {}

    for path in _python_files():
        for node in _tree(path).body:
            if isinstance(node, ast.ClassDef) and node.name in {
                "AgentDescriptor",
                "CapabilityDescriptor",
            }:
                descriptor_fields[node.name] = {
                    item.target.id
                    for item in node.body
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
                }

    assert descriptor_fields == {
        "AgentDescriptor": {
            "agent_id",
            "canonical_name",
            "role",
            "mission",
            "primary_capability_ids",
            "is_orchestrator",
        },
        "CapabilityDescriptor": {
            "capability_id",
            "canonical_name",
            "capability_class",
            "risk",
            "execution_route",
            "owner_agent",
        },
    }
    assert all(fields.isdisjoint(forbidden_fields) for fields in descriptor_fields.values())


def test_no_scheduler_state_or_duplicate_permission_engine_is_implemented() -> None:
    class_names = {
        node.name
        for path in _python_files()
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }

    assert class_names.isdisjoint(
        {
            "Scheduler",
            "RunState",
            "StepState",
            "PermissionEvaluator",
        }
    )


def test_registry_and_policy_have_no_runtime_third_party_dependency() -> None:
    allowed_roots = {
        "__future__",
        "backend",
        "collections",
        "dataclasses",
        "decimal",
        "enum",
        "math",
        "types",
        "typing",
    }
    imported_roots: set[str] = set()

    for path in _python_files():
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_roots.add(node.module.split(".")[0])

    assert imported_roots <= allowed_roots


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["dependencies"] == ["openai>=3.5,<4"]
