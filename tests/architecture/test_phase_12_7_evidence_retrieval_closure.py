from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.registry import (
    BASELINE_CAPABILITY_REGISTRY,
    CapabilityClass,
    CapabilityExecutionRoute,
)

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "backend" / "agent_runtime" / "agents" / "evidence"
RUNTIME = ROOT / "backend" / "agent_runtime" / "runtime"
ORCHESTRATION = ROOT / "backend" / "agent_runtime" / "orchestration"
SUPPORT_FAKE = ROOT / "tests" / "support" / "evidence_retrieval_fakes.py"
PIPELINE_TEST = ROOT / "tests" / "integration" / "test_ag02_search_rag_pipeline.py"
WORKFLOW_TEST = ROOT / "tests" / "integration" / "test_ag02_workflow_compatibility.py"
BASELINE_DOC = ROOT / "docs" / "development" / "PHASE_12_7_EVIDENCE_RETRIEVAL_BASELINE.md"


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


def _attribute_calls(path: Path) -> set[str]:
    return {
        node.func.attr
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def test_phase_f_closure_artifacts_are_present_in_the_authorized_layers() -> None:
    assert all(
        path.is_file()
        for path in (SUPPORT_FAKE, PIPELINE_TEST, WORKFLOW_TEST, BASELINE_DOC)
    )
    assert SUPPORT_FAKE.parent == ROOT / "tests" / "support"
    assert PIPELINE_TEST.parent == WORKFLOW_TEST.parent == ROOT / "tests" / "integration"


def test_evidence_production_has_no_runtime_or_orchestration_dependency() -> None:
    imported = {module for path in _python_files(EVIDENCE) for module in _imports(path)}
    assert all(not module.startswith("backend.agent_runtime.runtime") for module in imported)
    assert all(not module.startswith("backend.agent_runtime.orchestration") for module in imported)


def test_runtime_and_orchestration_have_no_evidence_agent_dependency() -> None:
    imported = {
        module
        for root in (RUNTIME, ORCHESTRATION)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all("backend.agent_runtime.agents.evidence" not in module for module in imported)


def test_phase_12_7_introduces_no_router_dispatcher_handler_or_store() -> None:
    forbidden_fragments = ("router", "dispatcher", "handler", "evidence_store")
    paths = _python_files(EVIDENCE)
    assert all(not any(fragment in path.stem.casefold() for fragment in forbidden_fragments) for path in paths)
    class_names = {
        node.name.casefold()
        for path in paths
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert all(not any(fragment in name for fragment in forbidden_fragments) for name in class_names)


def test_ag02_registry_ownership_is_exactly_e01_e02_e03() -> None:
    descriptors = BASELINE_CAPABILITY_REGISTRY.owned_by(AgentId.AG_02)
    assert tuple(item.capability_id.value for item in descriptors) == (
        "CAP-E01",
        "CAP-E02",
        "CAP-E03",
    )
    assert all(item.capability_class is CapabilityClass.EVIDENCE for item in descriptors)
    assert all(item.execution_route is CapabilityExecutionRoute.AGENT for item in descriptors)


def test_evidence_code_constructs_no_application_production_gate_or_permission() -> None:
    forbidden = {
        "ApplicationAction",
        "GateDecision",
        "PermissionScope",
        "ProductionCandidate",
        "ProductionRequest",
    }
    assert _calls(_python_files(EVIDENCE)).isdisjoint(forbidden)


def test_evidence_code_has_no_provider_framework_network_or_filesystem_imports() -> None:
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
        "subprocess",
        "urllib",
    }
    imported_roots = {
        module.split(".")[0]
        for path in _python_files(EVIDENCE)
        for module in _imports(path)
    }
    assert imported_roots.isdisjoint(forbidden_roots)


def test_evidence_code_has_no_retry_random_llm_or_unbounded_loop() -> None:
    paths = _python_files(EVIDENCE)
    source = "\n".join(path.read_text(encoding="utf-8").casefold() for path in paths)
    assert not any(isinstance(node, ast.While) for path in paths for node in ast.walk(_tree(path)))
    assert _calls(paths).isdisjoint({"backoff", "retry", "sleep", "uuid4"})
    assert all(token not in source for token in ("llm_reranker", "embedding_model", "provider_sdk"))


def test_search_and_materialization_remain_explicit_separate_operations() -> None:
    agent = EVIDENCE / "evidence_agent.py"
    tree = _tree(agent)
    search = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "search_evidence")
    fetch = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "fetch_evidence_item")
    search_calls = {
        node.func.attr
        for node in ast.walk(search)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    fetch_calls = {
        node.func.attr
        for node in ast.walk(fetch)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert search_calls == {"coordinate"}
    assert "fetch" in fetch_calls
    assert "search" not in fetch_calls and "coordinate" not in fetch_calls


def test_build_and_security_assessment_call_no_port_or_external_action() -> None:
    assert _attribute_calls(EVIDENCE / "evidence_agent.py").isdisjoint({"post", "put", "delete"})
    security_calls = _attribute_calls(EVIDENCE / "evidence_security.py")
    assert security_calls.isdisjoint({"fetch", "open", "request", "search", "urlopen"})


def test_expansion_preserves_initial_boundaries_and_cannot_execute_search() -> None:
    expansion = EVIDENCE / "evidence_expansion.py"
    source = expansion.read_text(encoding="utf-8")
    assert "scope=initial_request.scope" in source
    assert "source_policy=initial_request.source_policy" in source
    assert "filters=initial_request.filters" in source
    assert "required_authority=initial_request.required_authority" in source
    assert _attribute_calls(expansion).isdisjoint({"coordinate", "fetch", "search", "search_evidence"})


def test_recording_fakes_have_no_io_provider_retry_or_hidden_execution_loop() -> None:
    imported = set(_imports(SUPPORT_FAKE))
    assert not {module.split(".")[0] for module in imported} & {
        "httpx",
        "openai",
        "pathlib",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    tree = _tree(SUPPORT_FAKE)
    assert not any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree))
    assert _calls((SUPPORT_FAKE,)).isdisjoint({"backoff", "retry", "sleep"})


def test_integration_tests_use_fakes_not_real_provider_or_dispatch_modules() -> None:
    imports = {module for path in (PIPELINE_TEST, WORKFLOW_TEST) for module in _imports(path)}
    assert all("provider" not in module.casefold() for module in imports)
    assert all("dispatcher" not in module.casefold() for module in imports)
    assert "tests.support.evidence_retrieval_fakes" in imports
    assert "tests.support.orchestration_fakes" in imports


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == []
