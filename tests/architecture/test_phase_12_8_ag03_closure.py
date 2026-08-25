from __future__ import annotations

import ast
import tomllib
from dataclasses import MISSING, fields
from pathlib import Path

from backend.agent_runtime.agents.generation import (
    CorrectionMaterializationRequest,
    GenerationRepairProposal,
    GeneratorAgent,
    ProductionCandidateBuildRequest,
)
from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.registry import (
    BASELINE_AGENT_CAPABILITY_MATRIX,
    BASELINE_CAPABILITY_REGISTRY,
    AccessMode,
)

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
GENERATION = BACKEND / "agent_runtime" / "agents" / "generation"
RUNTIME = BACKEND / "agent_runtime" / "runtime"
ORCHESTRATION = BACKEND / "agent_runtime" / "orchestration"
SUPPORT_FAKE = ROOT / "tests" / "support" / "generation_fakes.py"
ORCHESTRATION_FAKE = ROOT / "tests" / "support" / "orchestration_fakes.py"
PIPELINE = ROOT / "tests" / "integration" / "test_ag03_generation_pipeline.py"
WORKFLOWS = ROOT / "tests" / "integration" / "test_ag03_workflow_compatibility.py"
BASELINE = ROOT / "docs" / "development" / "PHASE_12_8_AG03_BASELINE.md"


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
            isinstance(node, ast.ClassDef) and node.name == name
            for node in ast.walk(_tree(path))
        )
    )


def test_g_closure_artifacts_exist_only_in_docs_and_tests() -> None:
    assert all(
        path.is_file()
        for path in (SUPPORT_FAKE, PIPELINE, WORKFLOWS, BASELINE)
    )
    assert SUPPORT_FAKE.parent == ROOT / "tests" / "support"
    assert PIPELINE.parent == WORKFLOWS.parent == ROOT / "tests" / "integration"
    assert BASELINE.parent == ROOT / "docs" / "development"


def test_generation_production_imports_neither_runtime_nor_orchestration() -> None:
    imported = {
        module for path in _python_files(GENERATION) for module in _imports(path)
    }
    assert all(
        not module.startswith("backend.agent_runtime.runtime") for module in imported
    )
    assert all(
        not module.startswith("backend.agent_runtime.orchestration")
        for module in imported
    )


def test_runtime_and_orchestration_import_no_generation_agent() -> None:
    imported = {
        module
        for root in (RUNTIME, ORCHESTRATION)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all(
        not module.startswith("backend.agent_runtime.agents.generation")
        for module in imported
    )


def test_no_production_generation_dispatcher_router_handler_or_artifact_store() -> None:
    forbidden = {
        "GenerationStepRunner",
        "AgentCapabilityRouter",
        "AG03Handler",
        "ArtifactStore",
    }
    class_names = {
        node.name
        for path in _python_files(BACKEND)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert class_names.isdisjoint(forbidden)


def test_generation_boundary_has_one_port_protocol() -> None:
    sites = _class_sites("GenerationPort")
    assert sites == (GENERATION / "generation_ports.py",)
    node = next(
        node
        for node in ast.walk(_tree(sites[0]))
        if isinstance(node, ast.ClassDef) and node.name == "GenerationPort"
    )
    assert any(isinstance(base, ast.Name) and base.id == "Protocol" for base in node.bases)


def test_generation_boundary_has_one_coordinator() -> None:
    assert _class_sites("GenerationCoordinator") == (
        GENERATION / "generation_coordinator.py",
    )


def test_generation_boundary_has_one_output_guard() -> None:
    assert _class_sites("GenerationOutputGuard") == (
        GENERATION / "generation_guard.py",
    )


def test_canonical_candidate_and_correction_result_are_not_duplicated() -> None:
    assert _class_sites("ProductionCandidate") == (
        BACKEND
        / "agent_runtime"
        / "contracts"
        / "production"
        / "production_candidate.py",
    )
    assert _class_sites("CorrectionResult") == (
        BACKEND / "agent_runtime" / "contracts" / "review" / "correction_result.py",
    )


def test_ag03_registry_ownership_is_exactly_g01_g02_g03() -> None:
    descriptors = BASELINE_CAPABILITY_REGISTRY.owned_by(AgentId.AG_03)
    assert tuple(item.capability_id.value for item in descriptors) == (
        "CAP-G01",
        "CAP-G02",
        "CAP-G03",
    )


def test_ag03_direct_access_to_evidence_review_application_and_orchestration_is_denied() -> None:
    forbidden = tuple(
        descriptor.capability_id
        for descriptor in BASELINE_CAPABILITY_REGISTRY.all()
        if descriptor.capability_id.value.startswith(
            ("CAP-E", "CAP-V", "CAP-A", "CAP-O")
        )
    )
    rules = tuple(
        BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(AgentId.AG_03, capability)
        for capability in forbidden
    )
    assert all(rule.mode is AccessMode.DENY for rule in rules)


def test_generation_has_no_provider_network_sql_vector_or_filesystem_import() -> None:
    forbidden_roots = {
        "aiohttp",
        "chromadb",
        "faiss",
        "httpx",
        "langchain",
        "openai",
        "pathlib",
        "pinecone",
        "qdrant",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "urllib",
    }
    imported_roots = {
        module.split(".")[0]
        for path in _python_files(GENERATION)
        for module in _imports(path)
    }
    assert imported_roots.isdisjoint(forbidden_roots)


def test_generation_has_no_retry_backoff_sleep_or_unbounded_loop() -> None:
    paths = _python_files(GENERATION)
    assert not any(
        isinstance(node, ast.While)
        for path in paths
        for node in ast.walk(_tree(path))
    )
    assert _calls(paths).isdisjoint({"backoff", "retry", "sleep"})
    assert _attribute_calls(paths).isdisjoint({"backoff", "retry", "sleep"})


def test_generator_agent_has_no_review_validation_promotion_or_persistence_api() -> None:
    public = {
        name
        for name, value in GeneratorAgent.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert public.isdisjoint(
        {"persist", "promote", "review", "validate", "request_promotion"}
    )


def test_generation_imports_no_evidence_agent() -> None:
    imported = {
        module for path in _python_files(GENERATION) for module in _imports(path)
    }
    assert all("backend.agent_runtime.agents.evidence" not in module for module in imported)


def test_guard_assessment_remains_mandatory_for_both_materializations() -> None:
    for request_type in (
        ProductionCandidateBuildRequest,
        CorrectionMaterializationRequest,
    ):
        guard_field = next(
            item for item in fields(request_type) if item.name == "guard_assessment"
        )
        assert guard_field.default is MISSING
        assert guard_field.default_factory is MISSING
        assert "None" not in str(guard_field.type)


def test_repair_proposal_has_no_execution_surface() -> None:
    public = {
        name
        for name, value in GenerationRepairProposal.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert public.isdisjoint({"apply", "execute", "run", "retry"})


def test_test_runners_do_not_dispatch_generation_by_capability() -> None:
    runner_source = ORCHESTRATION_FAKE.read_text(encoding="utf-8")
    generation_fake_source = SUPPORT_FAKE.read_text(encoding="utf-8")
    assert "capability_id" not in runner_source
    assert "GeneratorAgent" not in runner_source
    assert "capability_id" not in generation_fake_source
    assert "GenerationCoordinator" not in generation_fake_source


def test_test_artifact_association_has_no_persistence_surface() -> None:
    source = SUPPORT_FAKE.read_text(encoding="utf-8")
    assert all(
        token not in source
        for token in ("filesystem", "serialize", "sql", "commit", "transaction")
    )
    assert _attribute_calls((SUPPORT_FAKE,)).isdisjoint(
        {"dump", "save", "write", "persist"}
    )


def test_rationalisation_records_no_safe_consolidation_and_deferred_dispatch() -> None:
    source = BASELINE.read_text(encoding="utf-8")
    assert "NO_SAFE_CONSOLIDATION_REQUIRED" in source
    assert "topology compatibility != production capability dispatch" in source
    assert "SOURCE_MATCH" in source
    assert "failure/replan policy" in source


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == []
