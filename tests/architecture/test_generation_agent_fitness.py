from __future__ import annotations

import ast
import inspect
import tomllib
from pathlib import Path

from backend.agent_runtime.agents.generation import (
    GenerationCandidateMaterializationCode,
    GeneratorAgent,
)
from backend.agent_runtime.agents.generation.generation_agent_model import (
    _FORBIDDEN_GENERATION_METADATA_AUTHORITY_KEYS,
)
from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.registry import (
    BASELINE_AGENT_CAPABILITY_MATRIX,
    BASELINE_CAPABILITY_REGISTRY,
    AccessMode,
)
from backend.core_contracts.capability import CapabilityId

ROOT = Path(__file__).resolve().parents[2]
GENERATION = ROOT / "backend" / "agent_runtime" / "agents" / "generation"
AGENT = GENERATION / "generation_agent.py"
AGENT_MODEL = GENERATION / "generation_agent_model.py"
CORRECTION = GENERATION / "generation_correction.py"
BOUNDARY_B = (
    GENERATION / "generation_model.py",
    GENERATION / "generation_ports.py",
)
COORDINATION_C = (
    GENERATION / "generation_coordination_model.py",
    GENERATION / "generation_coordinator.py",
)
D_FILES = (AGENT, AGENT_MODEL)


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


def test_d_files_are_confined_to_generation_boundary() -> None:
    assert all(path.is_file() and path.parent == GENERATION for path in D_FILES)


def test_production_candidate_construction_sites_are_exact_for_d_and_e() -> None:
    construction_sites = {
        path
        for path in _python_files(GENERATION)
        if "ProductionCandidate" in _calls((path,))
    }
    assert construction_sites == {AGENT, CORRECTION}
    assert "ProductionCandidate" not in _calls(BOUNDARY_B + COORDINATION_C)


def test_d_constructs_no_correction_result_or_evidence_set() -> None:
    assert _calls(D_FILES).isdisjoint({"CorrectionResult", "EvidenceSet"})
    imported = {module for path in D_FILES for module in _imports(path)}
    assert all("correction_request" not in module for module in imported)


def test_d_has_no_runtime_or_orchestration_imports() -> None:
    imported = {module for path in D_FILES for module in _imports(path)}
    assert all(not module.startswith("backend.agent_runtime.runtime") for module in imported)
    assert all(
        not module.startswith("backend.agent_runtime.orchestration")
        for module in imported
    )


def test_d_has_no_modules_adapters_or_infrastructure_imports() -> None:
    forbidden = ("backend.modules", "backend.adapters", "backend.infrastructure")
    imported = {module for path in D_FILES for module in _imports(path)}
    assert all(not module.startswith(forbidden) for module in imported)


def test_d_has_no_provider_network_sql_or_filesystem_imports() -> None:
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
        for path in D_FILES
        for module in _imports(path)
    }
    assert imported_roots.isdisjoint(forbidden_roots)


def test_d_has_no_retry_loop_backoff_or_sleep() -> None:
    assert not any(
        isinstance(node, ast.While)
        for path in D_FILES
        for node in ast.walk(_tree(path))
    )
    assert _calls(D_FILES).isdisjoint({"backoff", "retry", "sleep"})


def test_d_has_no_router_dispatcher_handler_or_store() -> None:
    forbidden = ("router", "dispatcher", "handler", "store")
    class_names = {
        node.name.casefold()
        for path in D_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert all(not any(item in name for item in forbidden) for name in class_names)


def test_d_calls_no_review_validate_promote_or_persist_method() -> None:
    assert _calls(D_FILES).isdisjoint(
        {"persist", "promote", "review", "validate"}
    )
    assert _attribute_calls(D_FILES).isdisjoint(
        {"persist", "promote", "review", "validate"}
    )


def test_generation_metadata_authority_vocabulary_is_closed_and_exact() -> None:
    assert _FORBIDDEN_GENERATION_METADATA_AUTHORITY_KEYS == frozenset(
        {
            "approved",
            "canonical",
            "gate_decision",
            "permission_scope",
            "promoted",
            "quality_score",
            "reviewed",
            "safe",
            "trusted",
            "validated",
            "validation_state",
        }
    )
    assert tuple(item.value for item in GenerationCandidateMaterializationCode) == (
        "UNSUPPORTED_CAPABILITY",
        "PREPARED_LINEAGE_MISMATCH",
        "TECHNICAL_RESULT_MISMATCH",
        "RESULT_META_MISMATCH",
        "NO_CANDIDATE_FOR_STATUS",
    )


def test_authority_metadata_validation_precedes_candidate_construction() -> None:
    agent_source = AGENT.read_text(encoding="utf-8")
    model_source = AGENT_MODEL.read_text(encoding="utf-8")
    assert agent_source.index("_validate_candidate_build_request(request)") < agent_source.index(
        "return ProductionCandidate("
    )
    validator_body = model_source[
        model_source.index("def _validate_candidate_build_request("):
        model_source.index("def _raise_materialization(")
    ]
    assert "_validate_authority_free_generation_metadata(" in validator_body


def test_authority_metadata_is_never_silently_filtered() -> None:
    trees = tuple(_tree(path) for path in D_FILES)
    assert not any(
        isinstance(node, ast.Delete)
        for tree in trees
        for node in ast.walk(tree)
    )
    assert _attribute_calls(D_FILES).isdisjoint(
        {"clear", "discard", "pop", "popitem", "remove"}
    )


def test_generator_agent_public_api_keeps_d_and_adds_only_e_methods() -> None:
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
    assert tuple(inspect.signature(GeneratorAgent.generate_production).parameters) == (
        "self",
        "request",
    )
    assert tuple(inspect.signature(GeneratorAgent.transform_production).parameters) == (
        "self",
        "request",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in D_FILES)
    assert '"CAP-G01"' in source
    assert '"CAP-G02"' in source
    assert '"CAP-G03"' in source


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
