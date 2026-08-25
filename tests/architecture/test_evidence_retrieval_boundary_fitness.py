from __future__ import annotations

import ast
import inspect
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.agents.evidence import (
    EvidenceDocumentContentPort,
    EvidenceSearchPort,
    RetrievalCandidate,
    RetrievalSignals,
)

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
AGENT_RUNTIME = BACKEND / "agent_runtime"
AGENTS = AGENT_RUNTIME / "agents"
EVIDENCE = AGENTS / "evidence"
RETRIEVAL_MODEL = EVIDENCE / "retrieval_model.py"
RETRIEVAL_PORTS = EVIDENCE / "retrieval_ports.py"
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


def _called_names(root: Path) -> set[str]:
    names: set[str] = set()
    for path in _python_files(root):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                names.add(node.func.id)
    return names


def test_agent_production_packages_are_limited_to_validated_boundaries() -> None:
    assert {path.name for path in AGENTS.iterdir() if path.name != "__pycache__"} == {
        "__init__.py",
        "evidence",
        "generation",
        "review",
    }
    assert {
        "__init__.py",
        "retrieval_model.py",
        "retrieval_ports.py",
    }.issubset(path.name for path in EVIDENCE.glob("*.py"))


def test_runtime_and_orchestration_do_not_depend_on_evidence_agents() -> None:
    imports = {
        module
        for root in (RUNTIME, ORCHESTRATION)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all("agent_runtime.agents" not in module for module in imports)


def test_evidence_boundary_has_no_forbidden_framework_or_provider_imports() -> None:
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
    imported = {module for path in _python_files(EVIDENCE) for module in _imports(path)}
    assert not {module.split(".")[0] for module in imported} & forbidden_roots
    assert all(not module.startswith(forbidden_backend_prefixes) for module in imported)


def test_evidence_boundary_has_no_io_network_subprocess_or_concurrency_imports() -> None:
    forbidden_roots = {
        "asyncio",
        "http",
        "multiprocessing",
        "pathlib",
        "socket",
        "subprocess",
        "threading",
        "urllib",
    }
    imported = {module for path in _python_files(EVIDENCE) for module in _imports(path)}
    assert not {module.split(".")[0] for module in imported} & forbidden_roots
    attributes = {
        node.attr
        for path in _python_files(EVIDENCE)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Attribute)
    }
    assert attributes.isdisjoint({"open", "read_text", "read_bytes"})


def test_evidence_boundary_constructs_no_public_evidence_or_runtime_workflow() -> None:
    boundary_calls = {
        node.func.id
        for path in (RETRIEVAL_MODEL, RETRIEVAL_PORTS)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert boundary_calls.isdisjoint(
        {
            "AgentInvocation",
            "DelegationEnvelope",
            "EvidenceItem",
            "EvidenceSet",
            "Plan",
            "PlanExecutor",
            "StepSpec",
        }
    )


def test_evidence_boundary_constructs_or_evaluates_no_permission_policy() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(EVIDENCE))
    assert "PermissionScope" not in source
    assert "SourcePolicyEngine" not in source
    assert "GateDecision" not in source
    assert _called_names(EVIDENCE).isdisjoint({"allow", "deny", "evaluate"})


def test_retrieval_models_expose_no_combined_truth_or_authority_score() -> None:
    signal_fields = {field.name for field in fields(RetrievalSignals)}
    candidate_fields = {field.name for field in fields(RetrievalCandidate)}
    assert signal_fields == {
        "structured_rank",
        "lexical_score",
        "semantic_score",
        "relational_score",
    }
    assert {"final_score", "truth_score", "authority_score"}.isdisjoint(
        signal_fields | candidate_fields
    )
    assert "content" not in candidate_fields


def test_ports_are_runtime_checkable_protocols_with_exact_operations() -> None:
    assert getattr(EvidenceSearchPort, "_is_protocol", False)
    assert getattr(EvidenceSearchPort, "_is_runtime_protocol", False)
    assert getattr(EvidenceDocumentContentPort, "_is_protocol", False)
    assert getattr(EvidenceDocumentContentPort, "_is_runtime_protocol", False)
    assert tuple(inspect.signature(EvidenceSearchPort.search).parameters) == (
        "self",
        "query",
        "channel",
    )
    assert tuple(inspect.signature(EvidenceDocumentContentPort.fetch).parameters) == (
        "self",
        "request",
    )


def test_no_production_port_implementation_or_separate_semantic_port_exists() -> None:
    classes = {
        node.name: tuple(base.id for base in node.bases if isinstance(base, ast.Name))
        for path in _python_files(EVIDENCE)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert classes["EvidenceSearchPort"] == ("Protocol",)
    assert classes["EvidenceDocumentContentPort"] == ("Protocol",)
    assert "SemanticPort" not in classes
    assert all(
        "EvidenceSearchPort" not in bases and "EvidenceDocumentContentPort" not in bases
        for name, bases in classes.items()
        if name not in {"EvidenceSearchPort", "EvidenceDocumentContentPort"}
    )


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == []
