from __future__ import annotations

import ast
import tomllib
from pathlib import Path
from typing import get_type_hints

from backend.agent_runtime.orchestration import WorkflowCatalog, WorkflowSelector

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
AGENT_RUNTIME = BACKEND / "agent_runtime"
ORCHESTRATION = AGENT_RUNTIME / "orchestration"
SELECTION = ORCHESTRATION / "selection"
RUNTIME = AGENT_RUNTIME / "runtime"


def _python_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


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


def _called_names(root: Path) -> set[str]:
    return {
        node.func.id
        for path in _python_files(root)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_selection_is_confined_to_its_orchestration_subpackage() -> None:
    assert SELECTION.is_dir()
    assert {path.name for path in SELECTION.glob("*.py")} == {
        "__init__.py",
        "model.py",
        "selector.py",
    }
    runtime_zones = {
        path.name
        for path in RUNTIME.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    }
    assert runtime_zones == {
        "planning",
        "state",
        "scheduling",
        "execution",
        "routing",
    }


def test_selection_imports_no_runtime_provider_transport_or_persistence() -> None:
    forbidden_roots = {
        "asyncio",
        "django",
        "fastapi",
        "flask",
        "httpx",
        "multiprocessing",
        "openai",
        "requests",
        "sqlalchemy",
        "sqlite3",
        "threading",
    }
    forbidden_backend_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
        "backend.agent_runtime.runtime",
    )
    imported = {
        module for path in _python_files(SELECTION) for module in _imports(path)
    }
    assert not {module.split(".")[0] for module in imported} & forbidden_roots
    assert all(not module.startswith(forbidden_backend_prefixes) for module in imported)


def test_selection_constructs_no_plan_step_delegation_or_invocation() -> None:
    calls = _called_names(SELECTION)
    assert calls.isdisjoint(
        {"Plan", "StepSpec", "DelegationEnvelope", "AgentInvocation"}
    )


def test_selection_uses_no_permission_gate_engine_or_concrete_handler() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(SELECTION)
    )
    forbidden_symbols = {
        "AccessMatrix",
        "CapabilityAuthorizationPolicy",
        "Coordinator",
        "GateEngine",
        "PermissionScope",
        "PlanCompiler",
        "ToolRegistry",
        "use_case_handler",
    }
    assert all(symbol not in source for symbol in forbidden_symbols)
    assert "llm" not in source.casefold()
    assert "rag" not in source.casefold()


def test_workflow_kind_keeps_one_definition_in_the_catalogue_model() -> None:
    definitions = [
        path.relative_to(ROOT).as_posix()
        for path in _python_files(BACKEND)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == "WorkflowKind"
    ]
    assert definitions == [
        "backend/agent_runtime/orchestration/workflows/model.py"
    ]


def test_selector_consumes_workflow_catalog_without_redefining_descriptors() -> None:
    assert get_type_hints(WorkflowSelector)["catalog"] is WorkflowCatalog
    assert "WorkflowTopologyDescriptor" not in _called_names(SELECTION)
    selector_tree = _tree(SELECTION / "selector.py")
    catalog_get_calls = [
        node
        for node in ast.walk(selector_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "catalog"
    ]
    assert len(catalog_get_calls) == 1


def test_runtime_does_not_import_or_embed_selection_rules() -> None:
    imported = {module for path in _python_files(RUNTIME) for module in _imports(path)}
    runtime_strings = {
        node.value
        for path in _python_files(RUNTIME)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert all("orchestration.selection" not in module for module in imported)
    assert all(not value.startswith("WF-") for value in runtime_strings)


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == ["openai>=3.5,<4"]
