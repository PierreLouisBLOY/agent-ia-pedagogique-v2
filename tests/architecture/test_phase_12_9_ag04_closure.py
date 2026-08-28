from __future__ import annotations

import ast
import inspect
import tomllib
from pathlib import Path

from backend.agent_runtime.agents.review import (
    CorrectionHandoffSignal,
    ReviewAssessmentSignal,
    ReviewCoordinator,
    ReviewerAgent,
    ReviewPort,
    ReviewSecurityGuard,
)
from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.registry import (
    BASELINE_AGENT_CAPABILITY_MATRIX,
    BASELINE_CAPABILITY_REGISTRY,
    AccessMode,
)

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
REVIEW = BACKEND / "agent_runtime" / "agents" / "review"
RUNTIME = BACKEND / "agent_runtime" / "runtime"
ORCHESTRATION = BACKEND / "agent_runtime" / "orchestration"
PIPELINE = ROOT / "tests" / "integration" / "test_ag04_review_pipeline.py"
WORKFLOWS = ROOT / "tests" / "integration" / "test_ag04_workflow_compatibility.py"
SUPPORT = ROOT / "tests" / "support" / "review_workflow_fakes.py"
BASELINE = ROOT / "docs" / "development" / "PHASE_12_9_AG04_BASELINE.md"


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> tuple[str, ...]:
    values: list[str] = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            values.append(node.module)
    return tuple(values)


def _calls(paths: tuple[Path, ...]) -> set[str]:
    values: set[str] = set()
    for path in paths:
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                values.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                values.add(node.func.attr)
    return values


def _class_sites(name: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _python_files(BACKEND)
        if any(
            isinstance(node, ast.ClassDef) and node.name == name
            for node in ast.walk(_tree(path))
        )
    )


def test_g_closure_artifacts_are_confined_to_tests_and_documentation() -> None:
    assert all(path.is_file() for path in (PIPELINE, WORKFLOWS, SUPPORT, BASELINE))
    assert PIPELINE.parent == WORKFLOWS.parent == ROOT / "tests" / "integration"
    assert SUPPORT.parent == ROOT / "tests" / "support"
    assert BASELINE.parent == ROOT / "docs" / "development"


def test_exactly_four_agents_and_ag04_owns_only_v01_v02() -> None:
    assert tuple(AgentId) == (
        AgentId.AG_01,
        AgentId.AG_02,
        AgentId.AG_03,
        AgentId.AG_04,
    )
    owned = BASELINE_CAPABILITY_REGISTRY.owned_by(AgentId.AG_04)
    assert tuple(item.capability_id.value for item in owned) == ("CAP-V01", "CAP-V02")
    assert all(item.capability_id.value != "CAP-V03" for item in owned)


def test_ag04_direct_e_g_a_o_access_is_denied() -> None:
    foreign = tuple(
        item.capability_id
        for item in BASELINE_CAPABILITY_REGISTRY.all()
        if item.capability_id.value.startswith(("CAP-E", "CAP-G", "CAP-A", "CAP-O"))
    )
    assert foreign
    assert all(
        BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(AgentId.AG_04, capability).mode
        is AccessMode.DENY
        for capability in foreign
    )


def test_review_core_security_and_signal_surfaces_are_unique() -> None:
    expected = {
        "ReviewPort": REVIEW / "review_ports.py",
        "ReviewCoordinator": REVIEW / "review_coordinator.py",
        "ReviewerAgent": REVIEW / "review_agent.py",
        "ReviewSecurityGuard": REVIEW / "review_security.py",
        "ReviewAssessmentSignal": REVIEW / "review_assessment_model.py",
        "CorrectionHandoffSignal": REVIEW / "review_assessment_model.py",
    }
    assert {name: _class_sites(name) for name in expected} == {
        name: (path,) for name, path in expected.items()
    }
    assert getattr(ReviewPort, "_is_protocol", False)
    assert tuple(inspect.signature(ReviewCoordinator.execute).parameters) == (
        "self",
        "prepared",
    )
    assert {name for name in ReviewSecurityGuard.__dict__ if not name.startswith("_")} == {
        "assess"
    }


def test_review_and_runtime_orchestration_have_zero_dependency_in_either_direction() -> None:
    review_imports = {
        module for path in _python_files(REVIEW) for module in _imports(path)
    }
    assert all(not module.startswith("backend.agent_runtime.runtime") for module in review_imports)
    assert all(
        not module.startswith("backend.agent_runtime.orchestration")
        for module in review_imports
    )
    outer_imports = {
        module
        for root in (RUNTIME, ORCHESTRATION)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all("backend.agent_runtime.agents.review" not in module for module in outer_imports)


def test_review_imports_no_application_domain_infrastructure_provider_or_io() -> None:
    forbidden_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
    )
    forbidden_roots = {
        "aiohttp",
        "chromadb",
        "faiss",
        "httpx",
        "openai",
        "pathlib",
        "qdrant",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "urllib",
    }
    imports = {module for path in _python_files(REVIEW) for module in _imports(path)}
    assert all(not module.startswith(forbidden_prefixes) for module in imports)
    assert {module.split(".")[0] for module in imports}.isdisjoint(forbidden_roots)
    assert _calls(_python_files(REVIEW)).isdisjoint(
        {"download", "eval", "exec", "open", "read_text", "run", "urlopen", "write_text"}
    )


def test_reviewer_has_review_only_api_and_constructs_no_c11_or_policy_authority() -> None:
    public = {
        name
        for name, value in ReviewerAgent.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert public == {"semantic_review", "build_review_result", "assess_findings"}
    assert public.isdisjoint(
        {"approve", "correct", "gate", "persist", "promote", "search", "validate"}
    )
    calls = _calls(_python_files(REVIEW))
    assert calls.isdisjoint(
        {"CorrectionRequest", "GateDecision", "PromotionPolicy", "ValidationResult"}
    )
    assert not hasattr(ReviewAssessmentSignal, "promote")
    assert not hasattr(CorrectionHandoffSignal, "build_correction_request")


def test_no_review_dispatcher_router_handler_store_or_local_retry_exists() -> None:
    forbidden_classes = {
        "ReviewStepRunner",
        "AgentCapabilityRouter",
        "AG04Handler",
        "ReviewArtifactStore",
        "PromotionEngine",
    }
    class_names = {
        node.name
        for path in _python_files(BACKEND)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert class_names.isdisjoint(forbidden_classes)
    calls = _calls(_python_files(REVIEW))
    assert calls.isdisjoint({"backoff", "replan", "retry", "sleep"})
    assert not any(
        isinstance(node, ast.While)
        for path in _python_files(REVIEW)
        for node in ast.walk(_tree(path))
    )
    backend_source = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(BACKEND)
    )
    assert "StepSpec -> ReviewerAgent" not in backend_source


def test_g_matrix_and_rationalisation_are_documented() -> None:
    source = BASELINE.read_text(encoding="utf-8")
    assert all(f"G{index}" in source for index in range(1, 11))
    assert "NO_SAFE_CONSOLIDATION_REQUIRED" in source
    assert "test-only" in source
    assert "12.9-H" in source
    assert "git rev-parse HEAD" in source


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == ["openai>=3.5,<4"]
