from __future__ import annotations

import ast
import tomllib
from dataclasses import MISSING, fields
from pathlib import Path

from backend.agent_runtime.agents.generation import (
    CorrectionMaterializationRequest,
    GenerationRepairProposal,
    ProductionCandidateBuildRequest,
)
from backend.agent_runtime.contracts.common import AgentId
from backend.agent_runtime.registry import (
    BASELINE_AGENT_CAPABILITY_MATRIX,
    BASELINE_CAPABILITY_REGISTRY,
    AccessMode,
)
from backend.core_contracts.capability import CapabilityId

ROOT = Path(__file__).resolve().parents[2]
GENERATION = ROOT / "backend" / "agent_runtime" / "agents" / "generation"
GUARD_MODEL = GENERATION / "generation_guard_model.py"
GUARD = GENERATION / "generation_guard.py"
AGENT_MODEL = GENERATION / "generation_agent_model.py"
AGENT = GENERATION / "generation_agent.py"
CORRECTION_MODEL = GENERATION / "generation_correction_model.py"
CORRECTION = GENERATION / "generation_correction.py"
GUARD_FILES = (GUARD_MODEL, GUARD)


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


def _function(path: Path, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.FunctionDef) and node.name == name
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


def _call_line(function: ast.FunctionDef, name: str) -> int:
    return next(
        node.lineno
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == name)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == name)
        )
    )


def test_guard_files_are_confined_to_generation_boundary() -> None:
    assert all(path.is_file() and path.parent == GENERATION for path in GUARD_FILES)


def test_guard_has_no_runtime_or_orchestration_dependency() -> None:
    imported = {module for path in GUARD_FILES for module in _imports(path)}
    assert all(not module.startswith("backend.agent_runtime.runtime") for module in imported)
    assert all(
        not module.startswith("backend.agent_runtime.orchestration")
        for module in imported
    )


def test_guard_has_no_module_adapter_infrastructure_or_agent_to_agent_dependency() -> None:
    forbidden = (
        "backend.modules",
        "backend.adapters",
        "backend.infrastructure",
        "backend.agent_runtime.agents.evidence",
    )
    imported = {module for path in GUARD_FILES for module in _imports(path)}
    assert all(not module.startswith(forbidden) for module in imported)


def test_guard_has_no_provider_network_sql_or_filesystem_import() -> None:
    forbidden_roots = {
        "aiohttp",
        "anthropic",
        "django",
        "fastapi",
        "google",
        "httpx",
        "langchain",
        "openai",
        "pathlib",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "urllib",
    }
    imported_roots = {
        module.split(".")[0]
        for path in GUARD_FILES
        for module in _imports(path)
    }
    assert imported_roots.isdisjoint(forbidden_roots)


def test_guard_constructs_no_review_gate_permission_or_evidence_search() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in GUARD_FILES)
    assert all(
        forbidden not in source
        for forbidden in (
            "AG04",
            "EvidenceSearchPort",
            "GateDecision",
            "PermissionScope",
            "ReviewResult",
        )
    )


def test_guard_has_no_loop_retry_fallback_backoff_sleep_or_generation_call() -> None:
    trees = tuple(_tree(path) for path in GUARD_FILES)
    assert not any(isinstance(node, ast.While) for tree in trees for node in ast.walk(tree))
    assert _calls(GUARD_FILES).isdisjoint(
        {"backoff", "fallback", "repair", "retry", "sleep"}
    )
    assert "generate" not in _attribute_calls(GUARD_FILES)


def test_repair_proposal_has_no_execution_surface() -> None:
    public = {
        name
        for name, value in GenerationRepairProposal.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert public.isdisjoint({"apply", "execute", "run"})


def test_scanner_cannot_follow_url_read_file_or_call_tool() -> None:
    imported = {module for path in GUARD_FILES for module in _imports(path)}
    assert "pathlib" not in imported
    assert _calls(GUARD_FILES).isdisjoint({"open", "urlopen"})
    assert _attribute_calls(GUARD_FILES).isdisjoint(
        {"click", "download", "fetch", "open", "request", "run", "write"}
    )


def test_materialization_requests_require_non_optional_guard_assessment() -> None:
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


def test_candidate_assessment_is_revalidated_before_candidate_construction() -> None:
    request_validator = _function(AGENT_MODEL, "_validate_candidate_build_request")
    assert _call_line(request_validator, "validate_generation_guard_assessment")
    build = _method(AGENT, "GeneratorAgent", "build_candidate")
    assert _call_line(build, "_validate_candidate_build_request") < _call_line(
        build,
        "ProductionCandidate",
    )


def test_correction_assessment_is_revalidated_before_both_outputs() -> None:
    request_validator = _function(
        CORRECTION_MODEL,
        "_validate_correction_materialization_request",
    )
    assert _call_line(request_validator, "validate_generation_guard_assessment")
    materialize = _function(CORRECTION, "materialize_correction")
    validation_line = _call_line(
        materialize,
        "_validate_correction_materialization_request",
    )
    assert validation_line < _call_line(materialize, "ProductionCandidate")
    assert validation_line < _call_line(materialize, "CorrectionResult")


def test_metadata_authority_guard_and_content_scanner_remain_separate() -> None:
    guard_source = GUARD.read_text(encoding="utf-8")
    agent_model_source = AGENT_MODEL.read_text(encoding="utf-8")
    assert "_validate_authority_free_generation_metadata" not in guard_source
    assert "_validate_authority_free_generation_metadata" in agent_model_source
    assert "_scan_security_signals" in guard_source


def test_registry_access_matrix_and_dependencies_remain_unchanged() -> None:
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
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == ["openai>=3.5,<4"]
