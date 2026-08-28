from __future__ import annotations

import ast
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.contracts import AgentId, ExecutorKind
from backend.agent_runtime.orchestration import (
    CoordinationAction,
    WorkflowCompletionDecision,
    WorkflowKind,
    WorkflowSelectionDecision,
    WorkflowSelector,
    WorkflowTopologyDescriptor,
)
from backend.agent_runtime.registry import BASELINE_AGENT_REGISTRY
from backend.agent_runtime.runtime import ExecutionDirectiveCode, PlanRevisionEngine

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
AGENT_RUNTIME = BACKEND / "agent_runtime"
ORCHESTRATION = AGENT_RUNTIME / "orchestration"
RUNTIME = AGENT_RUNTIME / "runtime"
COORDINATION = ORCHESTRATION / "coordination"


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


def _definitions(root: Path) -> set[str]:
    return {
        node.name
        for path in _python_files(root)
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }


def _called_names(root: Path) -> set[str]:
    return {
        node.func.id
        for path in _python_files(root)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_orchestration_has_exactly_four_production_subpackages() -> None:
    packages = {
        path.name
        for path in ORCHESTRATION.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    }
    assert packages == {"workflows", "selection", "compilation", "coordination"}
    assert all((ORCHESTRATION / package / "__init__.py").is_file() for package in packages)


def test_orchestration_defines_no_extra_engine_loop_agent_or_router() -> None:
    definitions = _definitions(ORCHESTRATION)
    forbidden_fragments = ("engine", "runtime_loop", "agentrunner", "router")
    assert all(
        not any(fragment in name.casefold() for fragment in forbidden_fragments)
        for name in definitions
    )


def test_runtime_never_imports_orchestration() -> None:
    imported = {module for path in _python_files(RUNTIME) for module in _imports(path)}
    assert all("backend.agent_runtime.orchestration" not in module for module in imported)


def test_orchestration_leaf_packages_do_not_import_root_facade() -> None:
    imported = {
        module for path in _python_files(ORCHESTRATION) for module in _imports(path)
    }
    assert "backend.agent_runtime.orchestration" not in imported


def test_orchestration_has_no_external_runtime_or_transport_dependency() -> None:
    forbidden_roots = {
        "aiohttp",
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
    imported_roots = {
        module.split(".", maxsplit=1)[0]
        for path in _python_files(ORCHESTRATION)
        for module in _imports(path)
    }
    assert imported_roots.isdisjoint(forbidden_roots)


def test_orchestration_has_no_business_repository_or_filesystem_access() -> None:
    imports = {
        module for path in _python_files(ORCHESTRATION) for module in _imports(path)
    }
    forbidden_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
        "backend.repositories",
    )
    assert all(not module.startswith(forbidden_prefixes) for module in imports)
    assert not {"os", "pathlib", "shutil"}.intersection(imports)
    assert _called_names(ORCHESTRATION).isdisjoint({"open", "exec", "eval"})


def test_orchestration_constructs_no_gate_decision_or_concrete_gate_engine() -> None:
    definitions = _definitions(ORCHESTRATION)
    calls = _called_names(ORCHESTRATION)
    assert definitions.isdisjoint({"GateDecision", "GateEngine"})
    assert calls.isdisjoint({"GateDecision", "GateEngine"})


def test_orchestration_constructs_no_handler_router_or_real_invocation() -> None:
    calls = _called_names(ORCHESTRATION)
    forbidden = {
        "AgentInvocation",
        "DelegationEnvelope",
        "ToolCallRequest",
        "ToolRouter",
        "UseCaseRequest",
        "UseCaseRouter",
    }
    assert calls.isdisjoint(forbidden)
    assert all("handler" not in name.casefold() for name in _definitions(ORCHESTRATION))


def test_coordinator_has_no_retry_loop_backoff_sleep_or_recovery_component() -> None:
    trees = [_tree(path) for path in _python_files(COORDINATION)]
    definitions = _definitions(COORDINATION)
    calls = _called_names(COORDINATION)
    assert not any(
        isinstance(node, ast.While) for tree in trees for node in ast.walk(tree)
    )
    assert calls.isdisjoint({"sleep", "backoff"})
    assert all(
        fragment not in name.casefold()
        for name in definitions
        for fragment in ("retryengine", "recovery", "snapshotstore", "circuitbreaker")
    )


def test_no_real_agent_or_fifth_agent_is_defined() -> None:
    assert tuple(item.agent_id for item in BASELINE_AGENT_REGISTRY.all()) == tuple(AgentId)
    assert [item.value for item in AgentId] == ["AG-01", "AG-02", "AG-03", "AG-04"]
    assert "AG-05" not in {item.value for item in AgentId}
    assert "AG_01" not in ExecutorKind.__members__
    assert not any(name.startswith("AG") for name in _definitions(ORCHESTRATION))


def test_workflow_metadata_contains_no_permission_or_authority_grant() -> None:
    descriptor_fields = {item.name for item in fields(WorkflowTopologyDescriptor)}
    assert descriptor_fields.isdisjoint(
        {
            "permission_scope",
            "permission_scope_ref",
            "access_matrix",
            "authority",
        }
    )


def test_completion_evaluator_remains_protocol_only() -> None:
    completion = COORDINATION / "completion.py"
    classes = {
        node.name: tuple(
            base.id for base in node.bases if isinstance(base, ast.Name)
        )
        for node in ast.walk(_tree(completion))
        if isinstance(node, ast.ClassDef)
    }
    assert classes["WorkflowCompletionEvaluator"] == ("Protocol",)
    assert not any(
        "WorkflowCompletionEvaluator" in bases
        for path in _python_files(ORCHESTRATION)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
        and node.name != "WorkflowCompletionEvaluator"
        for bases in [
            tuple(base.id for base in node.bases if isinstance(base, ast.Name))
        ]
    )


def test_plan_revision_engine_has_one_definition_in_runtime_only() -> None:
    definitions = [
        path.relative_to(ROOT).as_posix()
        for path in _python_files(BACKEND)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == "PlanRevisionEngine"
    ]
    assert definitions == ["backend/agent_runtime/runtime/planning/revision.py"]
    assert PlanRevisionEngine.__module__ == (
        "backend.agent_runtime.runtime.planning.revision"
    )


def test_distinct_phase_12_6_contracts_are_not_collapsed() -> None:
    assert WorkflowKind is not str
    assert WorkflowSelectionDecision is not WorkflowCompletionDecision
    assert ExecutionDirectiveCode is not CoordinationAction
    assert PlanRevisionEngine is not WorkflowSelector  # type: ignore[comparison-overlap]


def test_human_and_policy_gates_remain_catalogue_profiles_not_gate_decisions() -> None:
    from backend.agent_runtime.orchestration import (
        BASELINE_WORKFLOW_CATALOG,
        WorkflowGateProfile,
    )

    human = BASELINE_WORKFLOW_CATALOG.get(WorkflowKind.WF_10)
    policy = BASELINE_WORKFLOW_CATALOG.get(WorkflowKind.WF_11)
    assert human.gate_profile is WorkflowGateProfile.HUMAN and human.overlay
    assert policy.gate_profile is WorkflowGateProfile.POLICY_REQUIRED
    assert not policy.overlay


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == ["openai>=3.5,<4"]
