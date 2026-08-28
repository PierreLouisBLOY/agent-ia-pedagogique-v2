from __future__ import annotations

import ast
import inspect
import tomllib
from pathlib import Path

from backend.agent_runtime.agents.review import (
    ReviewerAgent,
    ReviewMaterializationErrorCode,
)
from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.registry import (
    BASELINE_AGENT_CAPABILITY_MATRIX,
    BASELINE_CAPABILITY_REGISTRY,
    AccessMode,
)
from backend.core_contracts.capability import CapabilityId

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
REVIEW = BACKEND / "agent_runtime" / "agents" / "review"
AGENT = REVIEW / "review_agent.py"
AGENT_MODEL = REVIEW / "review_agent_model.py"
D_FILES = (AGENT, AGENT_MODEL)
RUNTIME = BACKEND / "agent_runtime" / "runtime"
ORCHESTRATION = BACKEND / "agent_runtime" / "orchestration"


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
    return {
        node.func.id
        for path in paths
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _attribute_calls(paths: tuple[Path, ...]) -> set[str]:
    return {
        node.func.attr
        for path in paths
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def _class_sites(name: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _python_files(BACKEND)
        if any(
            isinstance(node, ast.ClassDef) and node.name == name for node in ast.walk(_tree(path))
        )
    )


def test_d_files_and_unique_review_surfaces_are_confined() -> None:
    assert all(path.is_file() and path.parent == REVIEW for path in D_FILES)
    assert _class_sites("ReviewerAgent") == (AGENT,)
    assert _class_sites("ReviewCoordinator") == (REVIEW / "review_coordinator.py",)
    assert _class_sites("ReviewPort") == (REVIEW / "review_ports.py",)


def test_canonical_review_models_and_enums_are_not_duplicated() -> None:
    expected = {
        "Finding": BACKEND / "agent_runtime" / "contracts" / "review" / "finding.py",
        "ReviewResult": (BACKEND / "agent_runtime" / "contracts" / "review" / "review_result.py"),
        "ReviewStatus": (BACKEND / "agent_runtime" / "contracts" / "review" / "review_result.py"),
        "ReviewDimension": (BACKEND / "agent_runtime" / "contracts" / "review" / "vocabulary.py"),
        "FindingSeverity": (BACKEND / "agent_runtime" / "contracts" / "review" / "vocabulary.py"),
        "OverallAssessment": (BACKEND / "agent_runtime" / "contracts" / "review" / "vocabulary.py"),
    }
    assert {name: _class_sites(name) for name in expected} == {
        name: (path,) for name, path in expected.items()
    }


def test_reviewer_agent_keeps_d_api_and_adds_only_e_assessment() -> None:
    public = {
        name
        for name, value in ReviewerAgent.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert public == {"semantic_review", "build_review_result", "assess_findings"}
    assert tuple(inspect.signature(ReviewerAgent.semantic_review).parameters) == (
        "self",
        "request",
    )
    assert tuple(inspect.signature(ReviewerAgent.build_review_result).parameters) == (
        "self",
        "request",
    )
    assert tuple(inspect.signature(ReviewerAgent.assess_findings).parameters) == (
        "self",
        "request",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in D_FILES)
    assert '"CAP-V01"' in source
    assert '"CAP-V02"' not in source


def test_d_has_no_runtime_or_orchestration_dependency_in_either_direction() -> None:
    imports = {module for path in D_FILES for module in _imports(path)}
    assert all(not module.startswith("backend.agent_runtime.runtime") for module in imports)
    assert all(not module.startswith("backend.agent_runtime.orchestration") for module in imports)
    outer_imports = {
        module
        for root in (RUNTIME, ORCHESTRATION)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all("agents.review" not in module for module in outer_imports)


def test_d_has_no_application_domain_adapter_or_infrastructure_imports() -> None:
    forbidden = (
        "backend.modules",
        "backend.adapters",
        "backend.infrastructure",
    )
    imports = {module for path in D_FILES for module in _imports(path)}
    assert all(not module.startswith(forbidden) for module in imports)


def test_d_has_no_provider_network_sql_vector_or_filesystem_imports() -> None:
    forbidden_roots = {
        "aiohttp",
        "anthropic",
        "asyncio",
        "chromadb",
        "django",
        "fastapi",
        "faiss",
        "google",
        "httpx",
        "langchain",
        "langgraph",
        "openai",
        "pathlib",
        "pinecone",
        "qdrant",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "threading",
        "urllib",
    }
    roots = {module.split(".")[0] for path in D_FILES for module in _imports(path)}
    assert roots.isdisjoint(forbidden_roots)


def test_d_has_no_retry_fallback_replan_or_resilience_loop() -> None:
    assert not any(
        isinstance(node, ast.While) for path in D_FILES for node in ast.walk(_tree(path))
    )
    assert _calls(D_FILES).isdisjoint({"backoff", "fallback", "replan", "repair", "retry", "sleep"})


def test_d_has_no_promotion_validation_persistence_search_or_routing_authority() -> None:
    forbidden = {
        "correct",
        "persist",
        "promote",
        "replan",
        "route",
        "search",
        "validate",
    }
    assert _calls(D_FILES).isdisjoint(forbidden)
    assert _attribute_calls(D_FILES).isdisjoint(forbidden)
    class_names = {
        node.name.casefold()
        for path in D_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert all(
        token not in name
        for name in class_names
        for token in ("dispatcher", "handler", "provider", "router", "store")
    )


def test_d_constructs_no_c11_gate_validation_or_promotion_contract() -> None:
    assert _calls(D_FILES).isdisjoint(
        {
            "CorrectionRequest",
            "CorrectionResult",
            "GateDecision",
            "PermissionScope",
            "ValidationResult",
        }
    )
    imports = {module for path in D_FILES for module in _imports(path)}
    assert all("correction_request" not in module for module in imports)
    assert all("correction_result" not in module for module in imports)


def test_d_does_not_reuse_generation_guard_or_evidence_security_scanner() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in D_FILES)
    assert "GenerationOutputGuard" not in source
    assert "EvidenceSecurityScanner" not in source
    imports = {module for path in D_FILES for module in _imports(path)}
    assert all("agents.generation" not in module for module in imports)
    assert all("agents.evidence" not in module for module in imports)


def test_closed_materialization_errors_add_no_policy_vocabulary() -> None:
    assert tuple(item.value for item in ReviewMaterializationErrorCode) == (
        "UNSUPPORTED_CAPABILITY",
        "NON_MATERIALIZABLE_STATUS",
        "STATUS_MISMATCH",
        "SOURCE_STEP_MISMATCH",
        "OPERATION_MISMATCH",
        "TARGET_MISMATCH",
        "INVALID_TECHNICAL_FINDING",
        "DUPLICATE_FINDING_ID",
        "FINDING_DIMENSION_OUT_OF_SCOPE",
        "FINDING_EVIDENCE_OUT_OF_SCOPE",
        "FINDING_EVIDENCE_NOT_USED",
        "INVALID_OVERALL_ASSESSMENT",
        "COVERAGE_OUT_OF_SCOPE",
        "MATERIALIZATION_MISMATCH",
    )
    assert {item.name for item in ReviewMaterializationErrorCode}.isdisjoint(
        {"BLOCKING_POLICY", "PROMOTION", "SCORE", "VALIDATION"}
    )


def test_d_constructs_canonical_findings_and_review_result_only_in_agent() -> None:
    assert "Finding" in _calls((AGENT_MODEL,))
    assert "ReviewResult" not in _calls((AGENT_MODEL,))
    assert "ReviewResult" in _calls((AGENT,))
    assert "Finding" not in _calls((AGENT,))


def test_registry_and_access_matrix_remain_exact_for_ag04() -> None:
    descriptors = BASELINE_CAPABILITY_REGISTRY.owned_by(AgentId.AG_04)
    assert tuple(item.capability_id.value for item in descriptors) == (
        "CAP-V01",
        "CAP-V02",
    )
    assert all(
        BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(
            AgentId.AG_04,
            CapabilityId(code),
        ).mode
        is AccessMode.ALLOW
        for code in ("CAP-V01", "CAP-V02")
    )


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == ["openai>=3.5,<4"]
