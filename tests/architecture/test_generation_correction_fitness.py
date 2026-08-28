from __future__ import annotations

import ast
import inspect
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.agents.generation import (
    CorrectionMaterializationCode,
    GenerationCoordinator,
    GenerationPort,
    GeneratorAgent,
    PreparedCorrectionCall,
)
from backend.agent_runtime.contracts import (
    AgentId,
    CorrectionRequest,
    CorrectionResult,
)
from backend.agent_runtime.registry import (
    BASELINE_AGENT_CAPABILITY_MATRIX,
    BASELINE_CAPABILITY_REGISTRY,
    AccessMode,
)
from backend.core_contracts.capability import CapabilityId

ROOT = Path(__file__).resolve().parents[2]
GENERATION = ROOT / "backend" / "agent_runtime" / "agents" / "generation"
CORRECTION = GENERATION / "generation_correction.py"
CORRECTION_MODEL = GENERATION / "generation_correction_model.py"
MODEL = GENERATION / "generation_model.py"
PORTS = GENERATION / "generation_ports.py"
COORDINATOR = GENERATION / "generation_coordinator.py"
E_FILES = (CORRECTION, CORRECTION_MODEL)


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


def test_correction_files_are_confined_to_generation_boundary() -> None:
    assert all(path.is_file() and path.parent == GENERATION for path in E_FILES)


def test_generation_keeps_one_outbound_port_and_no_second_provider_boundary() -> None:
    assert getattr(GenerationPort, "_is_protocol", False)
    protocol_classes = {
        node.name
        for path in _python_files(GENERATION)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
        and any(isinstance(base, ast.Name) and base.id == "Protocol" for base in node.bases)
    }
    assert protocol_classes == {"GenerationPort"}
    assert tuple(inspect.signature(GenerationPort.generate).parameters) == (
        "self",
        "request",
    )


def test_correction_has_no_repository_sql_network_or_filesystem_access() -> None:
    forbidden_roots = {
        "aiohttp",
        "httpx",
        "openai",
        "pathlib",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "urllib",
    }
    imported = {module for path in E_FILES for module in _imports(path)}
    assert {module.split(".")[0] for module in imported}.isdisjoint(forbidden_roots)
    source = "\n".join(path.read_text(encoding="utf-8").casefold() for path in E_FILES)
    assert all(token not in source for token in ("repository", "filesystem", "select "))


def test_correction_has_no_runtime_or_orchestration_imports() -> None:
    imported = {module for path in E_FILES for module in _imports(path)}
    assert all(not module.startswith("backend.agent_runtime.runtime") for module in imported)
    assert all(
        not module.startswith("backend.agent_runtime.orchestration")
        for module in imported
    )
    assert all(
        not module.startswith(("backend.modules", "backend.adapters", "backend.infrastructure"))
        for module in imported
    )


def test_correction_constructs_only_candidate_and_correction_result_contracts() -> None:
    calls = _calls(E_FILES)
    assert "ProductionCandidate" in calls
    assert "CorrectionResult" in calls
    assert calls.isdisjoint(
        {"ApplicationFailure", "ApplicationSuccess", "GateDecision", "ReviewResult"}
    )
    correction_result_sites = {
        path
        for path in _python_files(GENERATION)
        if "CorrectionResult" in _calls((path,))
    }
    assert correction_result_sites == {CORRECTION}


def test_canonical_c11_and_correction_result_shapes_remain_reused() -> None:
    assert tuple(item.name for item in fields(CorrectionRequest)) == (
        "meta",
        "target_production_ref",
        "review_ref",
        "finding_ids",
        "evidence_refs",
        "preserve_constraints",
        "allowed_changes",
        "forbidden_changes",
        "expected_delta",
    )
    assert tuple(item.name for item in fields(CorrectionResult)) == (
        "meta",
        "request",
        "new_production_ref",
        "parent_production_ref",
        "addressed_findings",
        "unresolved_findings",
        "change_summary",
        "lineage",
        "new_warnings",
    )


def test_prepared_correction_keeps_the_exact_preparation_snapshot_shape() -> None:
    assert tuple(item.name for item in fields(PreparedCorrectionCall)) == (
        "preparation_request",
        "capability_id",
        "correction_request",
        "target",
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


def test_prepared_correction_revalidates_all_caller_supplied_lineage() -> None:
    source = CORRECTION_MODEL.read_text(encoding="utf-8")
    validator = source[
        source.index("def _validate_prepared_correction_call("):
        source.index("def _validate_correction_technical_result(")
    ]
    assert 'technical.resolved_inputs["caller_resolved_inputs"]' in validator
    assert "snapshot.resolved_inputs" in validator
    assert "technical.output_contract != snapshot.output_contract" in validator


def test_prepared_correction_validation_happens_before_outbound() -> None:
    execute = _method(
        COORDINATOR,
        "GenerationCoordinator",
        "execute_correction",
    )
    validation_line = next(
        node.lineno
        for node in ast.walk(execute)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_validate_prepared_correction_call"
    )
    outbound_line = next(
        node.lineno
        for node in ast.walk(execute)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "generate"
    )
    assert validation_line < outbound_line


def test_correction_has_no_loop_retry_backoff_or_sleep() -> None:
    files = _python_files(GENERATION)
    assert not any(
        isinstance(node, ast.While)
        for path in files
        for node in ast.walk(_tree(path))
    )
    assert _calls(files).isdisjoint({"backoff", "retry", "sleep"})


def test_correction_calls_no_review_validate_promote_persist_or_gate() -> None:
    forbidden = {"gate", "persist", "promote", "review", "validate"}
    assert _calls(E_FILES).isdisjoint(forbidden)
    assert _attribute_calls(E_FILES).isdisjoint(forbidden)


def test_generator_agent_api_is_exact_through_e() -> None:
    public = {
        name
        for name, value in GeneratorAgent.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert public == {
        "build_candidate",
        "build_correction",
        "correct_production",
        "generate_production",
        "transform_production",
    }
    coordinator_public = {
        name
        for name, value in GenerationCoordinator.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert coordinator_public == {
        "execute",
        "execute_correction",
        "prepare",
        "prepare_correction",
    }


def test_correction_error_vocabulary_is_closed_and_authority_free() -> None:
    assert tuple(item.value for item in CorrectionMaterializationCode) == (
        "UNSUPPORTED_CAPABILITY",
        "TARGET_LINEAGE_MISMATCH",
        "PREPARED_LINEAGE_MISMATCH",
        "TECHNICAL_RESULT_MISMATCH",
        "CORRECTION_DETAILS_MISMATCH",
        "RESULT_META_MISMATCH",
        "NO_CORRECTION_FOR_STATUS",
    )


def test_registry_and_access_matrix_remain_unchanged_for_ag03() -> None:
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


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == ["openai>=3.5,<4"]
