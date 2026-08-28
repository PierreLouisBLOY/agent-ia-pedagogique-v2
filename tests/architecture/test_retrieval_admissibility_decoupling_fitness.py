from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "backend/agent_runtime/agents/evidence"
COORDINATOR = EVIDENCE / "retrieval_coordinator.py"
MODEL = EVIDENCE / "retrieval_coordination_model.py"
MATERIALIZATION_MODEL = EVIDENCE / "evidence_agent_model.py"
PORTS = EVIDENCE / "retrieval_ports.py"
SQLITE_SEARCH = ROOT / "backend/adapters/outbound/search/sqlite.py"
SQLITE_EVIDENCE = ROOT / "backend/adapters/outbound/evidence/sqlite.py"
ADR = ROOT / "architecture/adr/ADR-P12-061-retrieval-admissibility-decoupling.md"


def test_admissibility_is_explicit_and_not_an_exact_match_side_effect() -> None:
    ports = PORTS.read_text(encoding="utf-8")
    coordinator = COORDINATOR.read_text(encoding="utf-8")
    model = MODEL.read_text(encoding="utf-8")
    materialization_model = MATERIALIZATION_MODEL.read_text(encoding="utf-8")

    assert "class EvidenceAdmissibilityPort(Protocol)" in ports
    assert "port.is_admissible(candidate=candidate, query=query)" in coordinator
    assert "fallback_admissible_identities" in coordinator
    assert "admissible_identities = frozenset(occurrences_by_identity)" not in coordinator
    assert "a STRUCTURED occurrence is required" not in model
    assert "channel_ranks must contain STRUCTURED" not in model
    assert "channels must contain STRUCTURED" not in materialization_model


def test_sqlite_gate_proves_current_canonical_linkage_and_constraints() -> None:
    search = SQLITE_SEARCH.read_text(encoding="utf-8")
    evidence = SQLITE_EVIDENCE.read_text(encoding="utf-8")

    assert "JOIN object_registry AS registry" in search
    assert "sc.status = 'CURRENT'" in search
    assert "n.identity_status = 'CANONICAL'" in search
    assert "is_current_canonical_passage" in search
    assert "canonical_object_matches_level" in search
    assert "canonical_object_matches_topic" in search
    assert "_query_constraints_supported" in evidence
    assert 'dict(query.filters) != {"active": True}' in evidence
    assert 'kinds != ("canonical",)' in evidence


def test_f2a_introduces_no_provider_embedding_or_vector_dependency() -> None:
    paths = (COORDINATOR, MODEL, PORTS, SQLITE_SEARCH, SQLITE_EVIDENCE)
    forbidden_roots = {
        "anthropic",
        "chromadb",
        "faiss",
        "openai",
        "pinecone",
        "qdrant",
        "weaviate",
    }
    imports = {
        alias.name.split(".")[0]
        for path in paths
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (
            node.names
            if isinstance(node, ast.Import)
            else [ast.alias(name=node.module or "")]
        )
    }
    assert imports.isdisjoint(forbidden_roots)
    assert "embedding" not in "\n".join(
        path.read_text(encoding="utf-8").casefold() for path in paths
    )
    assert ADR.exists()
