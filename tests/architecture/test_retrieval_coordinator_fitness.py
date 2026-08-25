from __future__ import annotations

import ast
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.agents.evidence import (
    FusedRetrievalCandidate,
    RetrievalCoordinationResult,
)

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
AGENT_RUNTIME = BACKEND / "agent_runtime"
EVIDENCE = AGENT_RUNTIME / "agents" / "evidence"
COORDINATION_MODEL = EVIDENCE / "retrieval_coordination_model.py"
COORDINATOR = EVIDENCE / "retrieval_coordinator.py"
RUNTIME = AGENT_RUNTIME / "runtime"
ORCHESTRATION = AGENT_RUNTIME / "orchestration"


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


def _called_names(path: Path) -> set[str]:
    return {
        node.func.id
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_coordination_production_code_is_confined_to_evidence_agents() -> None:
    assert COORDINATION_MODEL.is_file()
    assert COORDINATOR.is_file()
    assert COORDINATION_MODEL.parent == EVIDENCE
    assert COORDINATOR.parent == EVIDENCE


def test_runtime_and_orchestration_do_not_depend_on_retrieval_coordination() -> None:
    imports = {
        module
        for root in (RUNTIME, ORCHESTRATION)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all("retrieval_coord" not in module for module in imports)


def test_coordination_has_no_forbidden_framework_or_boundary_imports() -> None:
    forbidden_roots = {
        "aiohttp",
        "anthropic",
        "chromadb",
        "django",
        "faiss",
        "fastapi",
        "httpx",
        "langchain",
        "langgraph",
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
    )
    imported = {
        module
        for path in (COORDINATION_MODEL, COORDINATOR)
        for module in _imports(path)
    }
    assert not {module.split(".")[0] for module in imported} & forbidden_roots
    assert all(not module.startswith(forbidden_backend_prefixes) for module in imported)


def test_coordination_has_no_io_network_subprocess_or_concurrency() -> None:
    forbidden_roots = {
        "asyncio",
        "http",
        "multiprocessing",
        "pathlib",
        "random",
        "socket",
        "subprocess",
        "threading",
        "time",
        "urllib",
    }
    imported = {
        module
        for path in (COORDINATION_MODEL, COORDINATOR)
        for module in _imports(path)
    }
    assert not {module.split(".")[0] for module in imported} & forbidden_roots
    attributes = {
        node.attr
        for path in (COORDINATION_MODEL, COORDINATOR)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Attribute)
    }
    assert attributes.isdisjoint({"open", "read_text", "read_bytes"})


def test_coordinator_constructs_no_evidence_document_content_or_runtime_workflow() -> None:
    calls = _called_names(COORDINATOR)
    assert calls.isdisjoint(
        {
            "AgentInvocation",
            "DelegationEnvelope",
            "DocumentContentResult",
            "EvidenceItem",
            "EvidenceSet",
            "PlanExecutor",
        }
    )
    result_fields = {field.name for field in fields(RetrievalCoordinationResult)}
    fused_fields = {field.name for field in fields(FusedRetrievalCandidate)}
    assert "content" not in result_fields | fused_fields
    assert "evidence_items" not in result_fields | fused_fields


def test_coordinator_never_fetches_document_content_or_searches_document_channel() -> None:
    tree = _tree(COORDINATOR)
    attribute_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    source = COORDINATOR.read_text(encoding="utf-8")
    assert "fetch" not in attribute_calls
    assert "EvidenceDocumentContentPort" not in source
    assert "RetrievalChannel.DOCUMENT" not in source


def test_coordination_has_no_permission_or_source_policy_authority() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (COORDINATION_MODEL, COORDINATOR)
    )
    assert "PermissionScope" not in source
    assert "AccessMatrix" not in source
    assert "SourcePolicyEngine" not in source
    assert _called_names(COORDINATOR).isdisjoint({"allow", "deny", "evaluate"})


def test_coordinator_has_no_retry_backoff_sleep_or_unbounded_loop() -> None:
    tree = _tree(COORDINATOR)
    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))
    assert _called_names(COORDINATOR).isdisjoint({"retry", "backoff", "sleep"})


def test_rank_fusion_uses_decimal_without_float_or_reranker() -> None:
    tree = _tree(COORDINATOR)
    source = COORDINATOR.read_text(encoding="utf-8").casefold()
    assert not any(
        isinstance(node, ast.Constant) and isinstance(node.value, float)
        for node in ast.walk(tree)
    )
    assert "float" not in _called_names(COORDINATOR)
    assert "decimal" in source
    assert all(
        forbidden not in source
        for forbidden in ("reranker", "cross_encoder", "query_expansion", "embedding_model")
    )


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == []
