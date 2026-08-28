from __future__ import annotations

import ast
import inspect
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.agents.generation import (
    GenerationCoordinationErrorCode,
    GenerationCoordinator,
    PreparedCorrectionCall,
    PreparedGenerationCall,
)
from backend.agent_runtime.contracts import ProductionRequest
from backend.agent_runtime.contracts.common import AgentId
from backend.agent_runtime.registry import (
    BASELINE_AGENT_CAPABILITY_MATRIX,
    BASELINE_CAPABILITY_REGISTRY,
    AccessMode,
)
from backend.core_contracts.capability import CapabilityId

ROOT = Path(__file__).resolve().parents[2]
GENERATION = ROOT / "backend" / "agent_runtime" / "agents" / "generation"
MODEL = GENERATION / "generation_coordination_model.py"
COORDINATOR = GENERATION / "generation_coordinator.py"
CONTRACTS = ROOT / "backend" / "agent_runtime" / "contracts"
REGISTRY = ROOT / "backend" / "agent_runtime" / "registry"


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


def _attribute_calls(paths: tuple[Path, ...]) -> tuple[str, ...]:
    return tuple(
        node.func.attr
        for path in paths
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
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


def test_coordination_files_are_confined_to_generation_boundary() -> None:
    assert MODEL.is_file() and MODEL.parent == GENERATION
    assert COORDINATOR.is_file() and COORDINATOR.parent == GENERATION


def test_coordination_has_no_runtime_or_orchestration_imports() -> None:
    imported = {module for path in (MODEL, COORDINATOR) for module in _imports(path)}
    assert all(not module.startswith("backend.agent_runtime.runtime") for module in imported)
    assert all(
        not module.startswith("backend.agent_runtime.orchestration") for module in imported
    )


def test_coordination_has_no_modules_adapters_or_infrastructure_imports() -> None:
    forbidden = ("backend.modules", "backend.adapters", "backend.infrastructure")
    imported = {module for path in (MODEL, COORDINATOR) for module in _imports(path)}
    assert all(not module.startswith(forbidden) for module in imported)


def test_coordination_has_no_provider_network_sql_or_filesystem_imports() -> None:
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
        for path in (MODEL, COORDINATOR)
        for module in _imports(path)
    }
    assert imported_roots.isdisjoint(forbidden_roots)


def test_coordination_has_no_while_retry_fallback_or_repair_loop() -> None:
    trees = (_tree(MODEL), _tree(COORDINATOR))
    assert not any(isinstance(node, ast.While) for tree in trees for node in ast.walk(tree))
    assert _calls((MODEL, COORDINATOR)).isdisjoint(
        {"backoff", "fallback", "repair", "retry", "sleep"}
    )


def test_coordination_constructs_no_candidate_correction_evidence_or_authority() -> None:
    assert _calls((MODEL, COORDINATOR)).isdisjoint(
        {
            "CorrectionResult",
            "EvidenceSet",
            "GateDecision",
            "PermissionScope",
            "ProductionCandidate",
        }
    )


def test_coordinator_does_not_import_correction_request_in_phase_c() -> None:
    imported = set(_imports(MODEL)) | set(_imports(COORDINATOR))
    assert all("correction_request" not in module for module in imported)


def test_coordination_has_no_router_dispatcher_handler_or_store() -> None:
    forbidden = ("router", "dispatcher", "handler", "store")
    class_names = {
        node.name.casefold()
        for path in (MODEL, COORDINATOR)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert all(not any(item in name for item in forbidden) for name in class_names)


def test_coordinator_has_exactly_one_outbound_call_per_execution_path() -> None:
    calls = [
        node
        for node in ast.walk(_tree(COORDINATOR))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "generate"
    ]
    assert len(calls) == 2
    execute = _method(COORDINATOR, "GenerationCoordinator", "execute")
    execute_calls = [
        node
        for node in ast.walk(execute)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "generate"
    ]
    assert len(execute_calls) == 1
    execute_correction = _method(
        COORDINATOR,
        "GenerationCoordinator",
        "execute_correction",
    )
    correction_calls = [
        node
        for node in ast.walk(execute_correction)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "generate"
    ]
    assert len(correction_calls) == 1


def test_execute_has_no_exception_translation_or_retry_branch() -> None:
    execute = _method(COORDINATOR, "GenerationCoordinator", "execute")
    assert not any(isinstance(node, (ast.Try, ast.While)) for node in ast.walk(execute))
    generate_line = next(
        node.lineno
        for node in ast.walk(execute)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "generate"
    )
    validation_line = next(
        node.lineno
        for node in ast.walk(execute)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_validate_prepared_call"
    )
    assert validation_line < generate_line


def test_coordination_calls_no_search_fetch_review_validate_or_promote() -> None:
    assert set(_attribute_calls((MODEL, COORDINATOR))).isdisjoint(
        {"fetch", "promote", "review", "search", "validate"}
    )


def test_capability_mapping_is_local_closed_and_registry_independent() -> None:
    source = MODEL.read_text(encoding="utf-8")
    assert 'capability_id.value == "CAP-G01"' in source
    assert 'capability_id.value == "CAP-G02"' in source
    assert 'capability_id.value == "CAP-G03"' in source
    assert "GenerationOperation.GENERATE" in source
    assert "GenerationOperation.TRANSFORM" in source
    assert "GenerationOperation.CORRECT" in source
    assert set(_imports(MODEL)).isdisjoint(
        {
            "backend.agent_runtime.registry",
            "backend.agent_runtime.registry.capabilities",
        }
    )


def test_pedagogical_context_lineage_is_explicit_and_revalidated() -> None:
    coordinator_source = COORDINATOR.read_text(encoding="utf-8")
    model_source = MODEL.read_text(encoding="utf-8")
    assert "pedagogical_context=canonical.pedagogical_context" in coordinator_source
    assert "technical.pedagogical_context" in model_source
    assert "canonical.pedagogical_context" in model_source
    assert "resolved_inputs" not in model_source[
        model_source.index("technical.pedagogical_context") : model_source.index(
            "technical.constraints"
        )
    ]


def test_prepared_generation_keeps_exact_preparation_snapshot_shape() -> None:
    assert tuple(item.name for item in fields(PreparedGenerationCall)) == (
        "preparation_request",
        "capability_id",
        "canonical_request",
        "port_request",
    )
    coordinator_source = COORDINATOR.read_text(encoding="utf-8")
    assert "preparation_request=request" in coordinator_source
    class_names = {
        node.name
        for path in _python_files(GENERATION)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert all("Snapshot" not in name for name in class_names)


def test_prepared_generation_revalidates_caller_supplied_lineage() -> None:
    source = MODEL.read_text(encoding="utf-8")
    validator = source[
        source.index("def _validate_prepared_call(") : source.index(
            "def _raise_mismatch("
        )
    ]
    assert "technical.resolved_inputs" in validator
    assert "snapshot.resolved_inputs" in validator
    assert "technical.output_contract" in validator
    assert "snapshot.output_contract" in validator


def test_g01_g02_and_g03_share_one_preparation_snapshot_pattern() -> None:
    assert fields(PreparedGenerationCall)[0].name == "preparation_request"
    assert fields(PreparedCorrectionCall)[0].name == "preparation_request"
    coordinator_source = COORDINATOR.read_text(encoding="utf-8")
    assert coordinator_source.count("preparation_request=request") == 2


def test_coordination_error_vocabulary_is_exact_and_authority_free() -> None:
    assert tuple(item.value for item in GenerationCoordinationErrorCode) == (
        "UNSUPPORTED_CAPABILITY",
        "CAPABILITY_OPERATION_MISMATCH",
        "TARGET_FORBIDDEN_FOR_GENERATE",
        "TARGET_REQUIRED_FOR_TRANSFORM",
        "CORRECTION_REQUEST_REQUIRED",
        "SOURCE_STEP_MISMATCH",
        "OPERATION_MISMATCH",
        "EVIDENCE_REF_OUT_OF_SCOPE",
        "DUPLICATE_EVIDENCE_REF_USED",
    )


def test_coordinator_public_signature_extends_with_explicit_correction_pair() -> None:
    public = {
        name
        for name, value in GenerationCoordinator.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert public == {
        "execute",
        "execute_correction",
        "prepare",
        "prepare_correction",
    }
    assert tuple(inspect.signature(GenerationCoordinator.prepare).parameters) == (
        "self",
        "request",
    )
    assert tuple(inspect.signature(GenerationCoordinator.execute).parameters) == (
        "self",
        "prepared",
    )
    assert tuple(
        inspect.signature(GenerationCoordinator.prepare_correction).parameters
    ) == ("self", "request")
    assert tuple(
        inspect.signature(GenerationCoordinator.execute_correction).parameters
    ) == ("self", "prepared")


def test_canonical_production_request_contract_shape_remains_reused() -> None:
    assert tuple(item.name for item in fields(ProductionRequest)) == (
        "meta",
        "production_kind",
        "brief",
        "output_format",
        "pedagogical_context",
        "constraints",
        "evidence_refs",
        "target_ref",
        "expected_sections",
    )


def test_registry_and_access_matrix_remain_exact_for_g01_g02_g03() -> None:
    descriptors = BASELINE_CAPABILITY_REGISTRY.owned_by(AgentId.AG_03)
    assert tuple(item.capability_id.value for item in descriptors) == (
        "CAP-G01",
        "CAP-G02",
        "CAP-G03",
    )
    assert all(
        BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(
            AgentId.AG_03,
            CapabilityId(code),
        ).mode
        is AccessMode.ALLOW
        for code in ("CAP-G01", "CAP-G02", "CAP-G03")
    )


def test_contract_and_registry_packages_do_not_import_generation_coordination() -> None:
    imported = {
        module
        for root in (CONTRACTS, REGISTRY)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all("agents.generation" not in module for module in imported)


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == ["openai>=3.5,<4"]
