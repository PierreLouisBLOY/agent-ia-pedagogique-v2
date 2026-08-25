from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from backend.agent_runtime.agents.evidence import (
    BASELINE_EVIDENCE_EXPANSION_POLICY,
)
from backend.agent_runtime.policy import BASELINE_AGENT_RUNTIME_POLICY

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "backend" / "agent_runtime" / "agents" / "evidence"
E_FILES = (
    EVIDENCE / "evidence_security_model.py",
    EVIDENCE / "evidence_security.py",
    EVIDENCE / "evidence_expansion_model.py",
    EVIDENCE / "evidence_expansion.py",
)
EXPANSION = EVIDENCE / "evidence_expansion.py"
EXPANSION_MODEL = EVIDENCE / "evidence_expansion_model.py"
SECURITY = EVIDENCE / "evidence_security.py"


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


def _called_names(path: Path) -> set[str]:
    return {
        node.func.id
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _attribute_calls(path: Path) -> set[str]:
    return {
        node.func.attr
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def test_phase_e_production_code_is_confined_to_evidence_package() -> None:
    assert all(path.is_file() and path.parent == EVIDENCE for path in E_FILES)


def test_phase_e_has_no_forbidden_framework_provider_or_boundary_imports() -> None:
    forbidden_roots = {
        "aiohttp",
        "chromadb",
        "django",
        "faiss",
        "fastapi",
        "httpx",
        "langchain",
        "openai",
        "pinecone",
        "qdrant",
        "requests",
        "sqlalchemy",
        "sqlite3",
        "weaviate",
    }
    forbidden_backend_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
        "backend.agent_runtime.orchestration",
        "backend.agent_runtime.runtime",
        "backend.agent_runtime.registry",
    )
    imported = {module for path in E_FILES for module in _imports(path)}
    assert not {module.split(".")[0] for module in imported} & forbidden_roots
    assert all(not module.startswith(forbidden_backend_prefixes) for module in imported)


def test_phase_e_has_no_io_network_url_parser_or_filesystem_access() -> None:
    forbidden_roots = {
        "http",
        "pathlib",
        "socket",
        "subprocess",
        "urllib",
    }
    imported = {module for path in E_FILES for module in _imports(path)}
    assert not {module.split(".")[0] for module in imported} & forbidden_roots
    forbidden_calls = {
        "fetch",
        "open",
        "read_bytes",
        "read_text",
        "request",
        "urlopen",
        "urlparse",
    }
    assert set().union(*(_attribute_calls(path) for path in E_FILES)).isdisjoint(
        forbidden_calls
    )


def test_phase_e_constructs_no_execution_permission_gate_or_global_event() -> None:
    forbidden = {
        "AccessMatrix",
        "AgentInvocation",
        "DelegationEnvelope",
        "EventBus",
        "GateDecision",
        "PermissionScope",
        "PlanExecutor",
        "PlanRevisionEngine",
        "SecurityEvent",
    }
    calls = set().union(*(_called_names(path) for path in E_FILES))
    assert calls.isdisjoint(forbidden)


def test_phase_e_has_no_retry_loop_random_uuid_llm_or_reranking() -> None:
    trees = tuple(_tree(path) for path in E_FILES)
    source = "\n".join(path.read_text(encoding="utf-8").casefold() for path in E_FILES)
    imported_roots = {
        module.split(".")[0] for path in E_FILES for module in _imports(path)
    }
    assert not any(
        isinstance(node, ast.While) for tree in trees for node in ast.walk(tree)
    )
    assert imported_roots.isdisjoint({"random", "time", "uuid"})
    assert set().union(*(_called_names(path) for path in E_FILES)).isdisjoint(
        {"backoff", "retry", "sleep", "uuid4"}
    )
    assert all(
        forbidden not in source
        for forbidden in ("embedding", "llm", "reranker", "semantic similarity")
    )


def test_expansion_advisor_cannot_search_fetch_or_coordinate() -> None:
    attribute_calls = _attribute_calls(EXPANSION)
    assert attribute_calls.isdisjoint(
        {"coordinate", "fetch", "search", "search_evidence"}
    )
    imported = set(_imports(EXPANSION))
    assert all("retrieval_coordinator" not in module for module in imported)
    assert all("evidence_agent" not in module for module in imported)


def test_global_upstream_warning_has_no_all_items_fallback() -> None:
    source = SECURITY.read_text(encoding="utf-8")
    function = next(
        node
        for node in ast.walk(_tree(SECURITY))
        if isinstance(node, ast.FunctionDef)
        and node.name == "_append_upstream_warning_signals"
    )
    function_source = ast.unparse(function)
    assert "or evidence_ids" not in function_source
    assert "UNATTRIBUTED_UPSTREAM_SECURITY_WARNING" in source


def test_advisor_validates_security_lineage_before_any_decision_branch() -> None:
    source = EXPANSION.read_text(encoding="utf-8")
    validation_index = source.index(
        "_validate_security_lineage(current=current, security=security)"
    )
    first_decision_index = source.index("if not need.required:")
    assert validation_index < first_decision_index
    assert "SECURITY_ASSESSMENT_LINEAGE_MISMATCH" in source


def test_round_record_carries_no_document_or_provider_payload() -> None:
    class_node = next(
        node
        for node in ast.walk(_tree(EXPANSION_MODEL))
        if isinstance(node, ast.ClassDef) and node.name == "EvidenceRoundRecord"
    )
    field_names = {
        node.target.id
        for node in class_node.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert field_names.isdisjoint(
        {"content", "excerpt", "prompt", "provider_payload"}
    )


def test_expansion_proposal_has_no_execution_or_authority_fields() -> None:
    class_node = next(
        node
        for node in ast.walk(_tree(EXPANSION_MODEL))
        if isinstance(node, ast.ClassDef) and node.name == "EvidenceExpansionProposal"
    )
    field_names = {
        node.target.id
        for node in class_node.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert field_names.isdisjoint(
        {
            "capability",
            "contract_meta",
            "gate_decision",
            "meta",
            "permission_scope",
            "step_id",
        }
    )


def test_expansion_baseline_is_linked_to_runtime_policy_and_three_rounds() -> None:
    assert BASELINE_EVIDENCE_EXPANSION_POLICY.max_rounds == 3
    assert (
        BASELINE_EVIDENCE_EXPANSION_POLICY.max_rounds
        == BASELINE_AGENT_RUNTIME_POLICY.max_evidence_rounds
    )
    source = EXPANSION_MODEL.read_text(encoding="utf-8")
    assert "BASELINE_AGENT_RUNTIME_POLICY.max_evidence_rounds" in source


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == []
