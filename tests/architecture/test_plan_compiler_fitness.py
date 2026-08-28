from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from backend.agent_runtime.contracts import ExecutorKind

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
AGENT_RUNTIME = BACKEND / "agent_runtime"
ORCHESTRATION = AGENT_RUNTIME / "orchestration"
COMPILATION = ORCHESTRATION / "compilation"
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


def test_plan_compiler_is_confined_to_orchestration_compilation() -> None:
    assert COMPILATION.is_dir()
    assert {path.name for path in COMPILATION.glob("*.py")} == {
        "__init__.py",
        "compiler.py",
        "model.py",
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


def test_compilation_has_no_provider_transport_persistence_or_concurrency_import() -> None:
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
    )
    imported = {
        module for path in _python_files(COMPILATION) for module in _imports(path)
    }
    assert not {module.split(".")[0] for module in imported} & forbidden_roots
    assert all(not module.startswith(forbidden_backend_prefixes) for module in imported)


def test_compiler_constructs_only_plan_and_steps_not_execution_contracts() -> None:
    calls = _called_names(COMPILATION)
    assert "Plan" in calls
    assert "StepSpec" in calls
    assert calls.isdisjoint(
        {
            "AgentInvocation",
            "DelegationEnvelope",
            "PlanExecutor",
            "PlanRevisionEngine",
            "StepRunner",
            "ToolCallRequest",
            "UseCaseRequest",
        }
    )


def test_compiler_constructs_or_evaluates_no_permission_or_concrete_handler() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(COMPILATION)
    )
    forbidden = {
        "AccessMatrix",
        "CapabilityAuthorizationPolicy",
        "GateEngine",
        "PermissionScope",
        "ToolRegistry",
        "handler",
    }
    assert all(symbol not in source for symbol in forbidden)
    assert "llm" not in source.casefold()
    assert "rag" not in source.casefold()


def test_compiler_reuses_plan_validator_after_plan_construction() -> None:
    tree = _tree(COMPILATION / "compiler.py")
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "validate"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "validator"
    ]
    assert len(calls) == 1


def test_capability_ownership_comes_from_canonical_registry_and_descriptors() -> None:
    source = (COMPILATION / "compiler.py").read_text(encoding="utf-8")
    assert "BASELINE_CAPABILITY_REGISTRY" in source
    assert "BASELINE_WORKFLOW_RESPONSIBILITY_DESCRIPTORS" in source
    assert "capability_registry.get" in source
    assert "allowed_capability_classes" in source
    assert "owner_agent" in source


def test_compiler_adds_no_agent_or_workflow_engine_vocabulary() -> None:
    class_names = {
        node.name
        for path in _python_files(COMPILATION)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(COMPILATION)
    )
    assert "AG-05" not in source
    assert "ExecutorKind.AG_01" not in source
    assert "WorkflowEngine" not in class_names
    assert not any(name.startswith("WF") and name.endswith("Engine") for name in class_names)
    assert "AG-01" not in {item.value for item in ExecutorKind}


def test_runtime_does_not_import_compilation_or_embed_composed_workflows() -> None:
    imported = {module for path in _python_files(RUNTIME) for module in _imports(path)}
    runtime_strings = {
        node.value
        for path in _python_files(RUNTIME)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert all("orchestration.compilation" not in module for module in imported)
    assert all("|overlay:" not in value for value in runtime_strings)


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == ["openai>=3.5,<4"]
