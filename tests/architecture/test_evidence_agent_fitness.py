from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
AGENT_RUNTIME = BACKEND / "agent_runtime"
EVIDENCE = AGENT_RUNTIME / "agents" / "evidence"
AGENT_MODEL = EVIDENCE / "evidence_agent_model.py"
AGENT = EVIDENCE / "evidence_agent.py"
RUNTIME = AGENT_RUNTIME / "runtime"
ORCHESTRATION = AGENT_RUNTIME / "orchestration"
CONTRACTS = AGENT_RUNTIME / "contracts"
REGISTRY = AGENT_RUNTIME / "registry"


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


def _function(path: Path, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _class(path: Path, name: str) -> ast.ClassDef:
    return next(
        node
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == name
    )


def _method(path: Path, class_name: str, method_name: str) -> ast.FunctionDef:
    class_node = _class(path, class_name)
    return next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )


def test_evidence_agent_production_code_is_confined_to_evidence_agents() -> None:
    assert AGENT_MODEL.is_file()
    assert AGENT.is_file()
    assert AGENT_MODEL.parent == EVIDENCE
    assert AGENT.parent == EVIDENCE


def test_runtime_orchestration_contracts_and_registry_do_not_depend_on_agent() -> None:
    imports = {
        module
        for root in (RUNTIME, ORCHESTRATION, CONTRACTS, REGISTRY)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all("evidence_agent" not in module for module in imports)


def test_evidence_agent_has_no_forbidden_framework_or_boundary_imports() -> None:
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
        module for path in (AGENT_MODEL, AGENT) for module in _imports(path)
    }
    assert not {module.split(".")[0] for module in imported} & forbidden_roots
    assert all(not module.startswith(forbidden_backend_prefixes) for module in imported)


def test_evidence_agent_has_no_io_network_subprocess_or_concurrency() -> None:
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
    imported = {
        module for path in (AGENT_MODEL, AGENT) for module in _imports(path)
    }
    assert not {module.split(".")[0] for module in imported} & forbidden_roots
    attributes = {
        node.attr
        for path in (AGENT_MODEL, AGENT)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Attribute)
    }
    assert attributes.isdisjoint({"open", "read_text", "read_bytes"})


def test_evidence_contracts_are_constructed_only_by_evidence_agent() -> None:
    construction_files = {
        path.relative_to(ROOT).as_posix()
        for path in _python_files(BACKEND)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"EvidenceItem", "EvidenceSet"}
    }
    assert construction_files == {
        "backend/agent_runtime/agents/evidence/evidence_agent.py"
    }


def test_agent_constructs_no_runtime_invocation_or_authority_object() -> None:
    calls = _called_names(AGENT)
    assert calls.isdisjoint(
        {
            "AccessMatrix",
            "AgentInvocation",
            "DelegationEnvelope",
            "PermissionScope",
            "PlanExecutor",
            "SourcePolicyEngine",
            "StepRunner",
        }
    )


def test_agent_has_no_retry_random_uuid_llm_or_unbounded_loop() -> None:
    trees = (_tree(AGENT_MODEL), _tree(AGENT))
    source = "\n".join(
        path.read_text(encoding="utf-8").casefold() for path in (AGENT_MODEL, AGENT)
    )
    imported_roots = {
        module.split(".")[0]
        for path in (AGENT_MODEL, AGENT)
        for module in _imports(path)
    }
    assert not any(
        isinstance(node, ast.While) for tree in trees for node in ast.walk(tree)
    )
    assert imported_roots.isdisjoint({"random", "time", "uuid"})
    assert _called_names(AGENT).isdisjoint({"retry", "backoff", "sleep", "uuid4"})
    assert all(
        forbidden not in source
        for forbidden in ("cross_encoder", "embedding_model", "llm_reranker")
    )


def test_search_evidence_only_delegates_to_coordinator() -> None:
    function = _function(AGENT, "search_evidence")
    called_names = {
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    attribute_calls = {
        node.func.attr
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert called_names.isdisjoint({"EvidenceItem", "EvidenceSet"})
    assert attribute_calls == {"coordinate"}


def test_content_fetch_occurs_only_in_fetch_evidence_item() -> None:
    functions_with_fetch = {
        node.name
        for node in ast.walk(_tree(AGENT))
        if isinstance(node, ast.FunctionDef)
        and any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "fetch"
            for child in ast.walk(node)
        )
    }
    assert functions_with_fetch == {"fetch_evidence_item"}


def test_build_evidence_set_calls_no_port_and_no_automatic_capability_loop() -> None:
    function = _function(AGENT, "build_evidence_set")
    attribute_calls = {
        node.func.attr
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert attribute_calls.isdisjoint({"coordinate", "fetch", "search"})
    public_methods = {
        node.name
        for node in ast.walk(_tree(AGENT))
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    }
    assert public_methods == {
        "assess_evidence_coverage",
        "build_evidence_set",
        "detect_version_conflicts",
        "fetch_evidence_item",
        "search_evidence",
    }
    assert public_methods.isdisjoint(
        {"execute", "retrieve_everything", "run", "search_and_fetch_all"}
    )


def test_fetch_request_has_only_explicit_request_retrieval_lineage() -> None:
    class_node = _class(AGENT_MODEL, "EvidenceFetchRequest")
    fields = tuple(
        node.target.id
        for node in class_node.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    )
    assert fields == ("evidence_id", "request", "retrieval", "candidate")
    assert "source_policy" not in fields


def test_fetch_validates_lineage_before_port_and_inherits_retrieval_policy() -> None:
    function = _method(AGENT, "EvidenceAgent", "fetch_evidence_item")
    validation_calls = {
        node.func.id: node.lineno
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id
        in {"validate_retrieval_lineage", "_validate_candidate_membership"}
    }
    fetch_lines = [
        node.lineno
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "fetch"
    ]
    assert set(validation_calls) == {
        "validate_retrieval_lineage",
        "_validate_candidate_membership",
    }
    assert fetch_lines and max(validation_calls.values()) < min(fetch_lines)

    content_request = next(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "DocumentContentRequest"
    )
    source_policy = next(
        keyword.value
        for keyword in content_request.keywords
        if keyword.arg == "source_policy"
    )
    assert ast.unparse(source_policy) == "request.retrieval.query.source_policy"


def test_build_request_validates_request_to_retrieval_lineage() -> None:
    post_init = _method(AGENT_MODEL, "EvidenceSetBuildRequest", "__post_init__")
    calls = {
        node.func.id
        for node in ast.walk(post_init)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "validate_retrieval_lineage" in calls


def test_provenance_keeps_lineage_without_copying_document_content() -> None:
    fetch = _method(AGENT, "EvidenceAgent", "fetch_evidence_item")
    provenance = next(
        node.value
        for node in fetch.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "provenance"
            for target in node.targets
        )
    )
    assert isinstance(provenance, ast.Dict)
    provenance_keys = {
        key.value
        for key in provenance.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    assert {
        "retrieval_candidate_id",
        "retrieval_identity_key",
        "retrieval_channels",
        "retrieval_candidate_provenance",
        "content_provenance",
        "content_metadata",
        "candidate_metadata",
        "source_ref",
        "locator",
        "resolved_version_or_checksum",
    } <= provenance_keys
    assert "content" not in provenance_keys
    assert "excerpt_or_summary" not in provenance_keys
    assert all(ast.unparse(node) != "content.content" for node in ast.walk(provenance))

    build = _method(AGENT, "EvidenceAgent", "build_evidence_set")
    source = ast.unparse(build)
    assert "'item_lineage'" in source
    assert 'item.item.excerpt_or_summary' not in source


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == ["openai>=3.5,<4"]
