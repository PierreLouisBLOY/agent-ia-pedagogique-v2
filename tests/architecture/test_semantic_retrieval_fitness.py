from __future__ import annotations

import ast
import inspect
import tomllib
from pathlib import Path

from backend.adapters.outbound.evidence.sqlite import SQLiteEvidenceSearchAdapter
from backend.adapters.outbound.semantic import (
    EmbeddingTransport,
    SQLiteSemanticSearchBackend,
)
from backend.agent_runtime.agents.evidence import (
    EvidenceAdmissibilityPort,
    EvidenceSearchPort,
)
from backend.agent_runtime.agents.evidence.retrieval_coordination_model import (
    BASELINE_RETRIEVAL_COORDINATION_POLICY,
)
from backend.agent_runtime.registry import BASELINE_TOOL_REGISTRY
from backend.core_contracts.capability import CapabilityId

ROOT = Path(__file__).resolve().parents[2]
SEMANTIC_ROOT = ROOT / "backend" / "adapters" / "outbound" / "semantic"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_semantic_is_an_internal_transport_under_existing_evidence_ports() -> None:
    assert inspect.signature(EvidenceSearchPort.search).parameters.keys() == {
        "self",
        "query",
        "channel",
    }
    assert inspect.signature(EvidenceAdmissibilityPort.is_admissible).parameters.keys() == {
        "self",
        "candidate",
        "query",
    }
    assert inspect.signature(EmbeddingTransport.embed).parameters.keys() == {
        "self",
        "request",
    }
    assert SQLiteEvidenceSearchAdapter is not SQLiteSemanticSearchBackend
    assert not (ROOT / "backend" / "agent_runtime" / "semantic").exists()


def test_semantic_keeps_f2a_fusion_policy_and_capability_registry_unchanged() -> None:
    assert BASELINE_RETRIEVAL_COORDINATION_POLICY.channel_limit == 20
    assert BASELINE_RETRIEVAL_COORDINATION_POLICY.final_limit == 10
    assert BASELINE_RETRIEVAL_COORDINATION_POLICY.rrf_k == 60
    assert BASELINE_TOOL_REGISTRY.by_capability(CapabilityId("CAP-T04")) == ()


def test_semantic_adapter_uses_only_standard_library_and_existing_openai_sdk() -> None:
    forbidden = {
        "chromadb",
        "faiss",
        "hnswlib",
        "langchain",
        "litellm",
        "llama_index",
        "numpy",
        "pgvector",
        "qdrant_client",
        "sentence_transformers",
        "sqlite_vec",
    }
    imports = {
        name
        for path in SEMANTIC_ROOT.glob("*.py")
        for name in _imports(path)
    }
    assert not imports.intersection(forbidden)

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["dependencies"] == ["openai>=3.5,<4"]


def test_semantic_index_is_not_a_tracked_runtime_artifact() -> None:
    tracked_sources = tuple(
        path
        for owner in (
            ROOT / "architecture",
            ROOT / "backend",
            ROOT / "database",
            ROOT / "docs",
        )
        for path in owner.rglob("*")
        if path.is_file()
        and path.suffix in {".sqlite", ".sqlite3", ".db"}
    )
    assert tracked_sources == ()
