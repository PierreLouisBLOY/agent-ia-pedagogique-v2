from __future__ import annotations

import ast
import inspect
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.agents.review import (
    PreparedReviewCall,
    ReviewCoordinationErrorCode,
    ReviewCoordinator,
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
MODEL = REVIEW / "review_coordination_model.py"
COORDINATOR = REVIEW / "review_coordinator.py"
CONTRACTS = BACKEND / "agent_runtime" / "contracts"
REGISTRY = BACKEND / "agent_runtime" / "registry"
RUNTIME = BACKEND / "agent_runtime" / "runtime"
ORCHESTRATION = BACKEND / "agent_runtime" / "orchestration"


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> tuple[str, ...]:
    imported: list[str] = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    return tuple(imported)


def _calls(paths: tuple[Path, ...]) -> set[str]:
    return {
        node.func.id
        for path in paths
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _class_sites(name: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _python_files(BACKEND)
        if any(
            isinstance(node, ast.ClassDef) and node.name == name for node in ast.walk(_tree(path))
        )
    )


def _method(path: Path, class_name: str, method_name: str) -> ast.FunctionDef:
    class_node = next(
        node
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )


def test_coordination_files_and_coordinator_are_unique_and_confined() -> None:
    assert MODEL.is_file() and MODEL.parent == REVIEW
    assert COORDINATOR.is_file() and COORDINATOR.parent == REVIEW
    assert _class_sites("ReviewCoordinator") == (COORDINATOR,)
    assert _class_sites("ReviewPort") == (REVIEW / "review_ports.py",)


def test_phase_c_creates_no_reviewer_agent_provider_or_runtime_dispatcher() -> None:
    names = {
        node.name
        for path in (MODEL, COORDINATOR)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert "ReviewerAgent" not in names
    assert all("Provider" not in name for name in names)
    assert all("Dispatcher" not in name for name in names)
    assert all("Handler" not in name for name in names)


def test_coordination_does_not_cross_runtime_or_orchestration_boundaries() -> None:
    imports = {module for path in (MODEL, COORDINATOR) for module in _imports(path)}
    assert all(not module.startswith("backend.agent_runtime.runtime") for module in imports)
    assert all(not module.startswith("backend.agent_runtime.orchestration") for module in imports)
    outer_imports = {
        module
        for root in (RUNTIME, ORCHESTRATION)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all("agents.review" not in module for module in outer_imports)


def test_coordination_has_no_business_adapter_or_infrastructure_imports() -> None:
    forbidden = ("backend.modules", "backend.adapters", "backend.infrastructure")
    imports = {module for path in (MODEL, COORDINATOR) for module in _imports(path)}
    assert all(not module.startswith(forbidden) for module in imports)


def test_coordination_has_no_provider_network_sql_vector_or_filesystem_imports() -> None:
    forbidden_roots = {
        "aiohttp",
        "anthropic",
        "asyncio",
        "chromadb",
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
    roots = {module.split(".")[0] for path in (MODEL, COORDINATOR) for module in _imports(path)}
    assert roots.isdisjoint(forbidden_roots)


def test_coordination_has_no_loop_retry_fallback_or_exception_translation() -> None:
    trees = (_tree(MODEL), _tree(COORDINATOR))
    assert not any(
        isinstance(node, (ast.For, ast.AsyncFor, ast.While))
        for tree in trees
        for node in ast.walk(tree)
    )
    assert _calls((MODEL, COORDINATOR)).isdisjoint(
        {"backoff", "fallback", "repair", "retry", "sleep"}
    )
    execute = _method(COORDINATOR, "ReviewCoordinator", "execute")
    assert not any(isinstance(node, (ast.Try, ast.While)) for node in ast.walk(execute))


def test_execute_has_exactly_one_outbound_review_call_after_prevalidation() -> None:
    execute = _method(COORDINATOR, "ReviewCoordinator", "execute")
    calls = [
        node
        for node in ast.walk(execute)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "review"
    ]
    assert len(calls) == 1
    validation_line = next(
        node.lineno
        for node in ast.walk(execute)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_validate_prepared_review_call"
    )
    assert validation_line < calls[0].lineno


def test_capability_mapping_is_local_closed_and_registry_independent() -> None:
    source = MODEL.read_text(encoding="utf-8")
    assert 'capability_id.value == "CAP-V01"' in source
    assert 'capability_id.value == "CAP-V02"' in source
    assert "ReviewOperation.SEMANTIC_REVIEW" in source
    assert "ReviewOperation.ASSESS_FINDINGS" in source
    assert all("agent_runtime.registry" not in module for module in _imports(MODEL))


def test_prepared_snapshot_shape_and_public_api_are_exact() -> None:
    assert tuple(item.name for item in fields(PreparedReviewCall)) == (
        "preparation_request",
        "capability_id",
        "canonical_request",
        "target",
        "port_request",
    )
    public = {
        name
        for name, value in ReviewCoordinator.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert public == {"prepare", "execute"}
    assert tuple(inspect.signature(ReviewCoordinator.prepare).parameters) == (
        "self",
        "request",
    )
    assert tuple(inspect.signature(ReviewCoordinator.execute).parameters) == (
        "self",
        "prepared",
    )


def test_coverage_lineage_is_explicit_and_revalidated_per_subcontext() -> None:
    model_source = MODEL.read_text(encoding="utf-8")
    coordinator_source = COORDINATOR.read_text(encoding="utf-8")
    for name in (
        "severity_policy",
        "context_slice",
        "independence_requirements",
    ):
        assert f'"{name}": request.{name}' in model_source
    assert "technical.coverage_context" in model_source
    assert "_coverage_context_for(canonical)" in model_source
    assert "coverage_context=_coverage_context_for(canonical)" in coordinator_source


def test_prepared_snapshot_revalidates_all_caller_and_canonical_lineage() -> None:
    source = MODEL.read_text(encoding="utf-8")
    required = (
        "snapshot.capability_id",
        "snapshot.request",
        "snapshot.target",
        "technical.target_content",
        "technical.target_payload",
        "technical.review_dimensions",
        "technical.criteria",
        "technical.evidence_refs",
        "technical.resolved_inputs",
        "snapshot.resolved_inputs",
        "technical.output_contract",
        "snapshot.output_contract",
        "technical.review_budget",
    )
    assert all(item in source for item in required)


def test_coordination_does_not_materialize_canonical_review_outputs_or_authority() -> None:
    assert _calls((MODEL, COORDINATOR)).isdisjoint(
        {
            "Finding",
            "ReviewResult",
            "CorrectionRequest",
            "GateDecision",
            "PermissionScope",
        }
    )
    source = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in (MODEL, COORDINATOR)
    )
    assert all(
        token not in source
        for token in (
            "api_key",
            "endpoint_url",
            "prompt_template",
            "provider_response",
            "revieweragent",
        )
    )


def test_coordination_does_not_reuse_generation_or_evidence_security_engines() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in (MODEL, COORDINATOR))
    assert "GenerationOutputGuard" not in source
    assert "EvidenceSecurityScanner" not in source
    imports = {module for path in (MODEL, COORDINATOR) for module in _imports(path)}
    assert all("agents.generation" not in module for module in imports)
    assert all("agents.evidence" not in module for module in imports)


def test_coordination_error_vocabulary_is_exact_and_authority_free() -> None:
    assert tuple(item.value for item in ReviewCoordinationErrorCode) == (
        "UNSUPPORTED_CAPABILITY",
        "CAPABILITY_OPERATION_MISMATCH",
        "TARGET_REF_MISMATCH",
        "SOURCE_STEP_MISMATCH",
        "OPERATION_MISMATCH",
        "EVIDENCE_REF_OUT_OF_SCOPE",
        "DUPLICATE_EVIDENCE_REF_USED",
        "PREPARATION_MISMATCH",
    )


def test_registry_and_access_matrix_remain_exact_for_v01_v02() -> None:
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


def test_contract_registry_runtime_and_orchestration_do_not_import_coordination() -> None:
    imports = {
        module
        for root in (CONTRACTS, REGISTRY, RUNTIME, ORCHESTRATION)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all("agents.review" not in module for module in imports)


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == []
