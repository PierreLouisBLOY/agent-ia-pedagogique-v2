from __future__ import annotations

import ast
import inspect
import tomllib
from pathlib import Path

from backend.agent_runtime.agents.review import ReviewerAgent

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
REVIEW = BACKEND / "agent_runtime" / "agents" / "review"
ASSESSMENT = REVIEW / "review_assessment.py"
ASSESSMENT_MODEL = REVIEW / "review_assessment_model.py"
E_FILES = (ASSESSMENT, ASSESSMENT_MODEL)
RUNTIME = BACKEND / "agent_runtime" / "runtime"
ORCHESTRATION = BACKEND / "agent_runtime" / "orchestration"


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


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


def _class_sites(name: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _python_files(BACKEND)
        if any(
            isinstance(node, ast.ClassDef) and node.name == name
            for node in ast.walk(_tree(path))
        )
    )


def _function(path: Path, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_e_files_are_confined_and_core_review_surfaces_remain_unique() -> None:
    assert all(path.is_file() and path.parent == REVIEW for path in E_FILES)
    assert _class_sites("ReviewerAgent") == (REVIEW / "review_agent.py",)
    assert _class_sites("ReviewCoordinator") == (REVIEW / "review_coordinator.py",)
    assert _class_sites("ReviewPort") == (REVIEW / "review_ports.py",)


def test_reviewer_agent_exposes_only_v01_v02_and_c10_build_surfaces() -> None:
    public = {
        name
        for name, value in ReviewerAgent.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert public == {"semantic_review", "build_review_result", "assess_findings"}
    assert tuple(inspect.signature(ReviewerAgent.assess_findings).parameters) == (
        "self",
        "request",
    )
    package_source = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(REVIEW)
    )
    assert '"CAP-V01"' in package_source
    assert '"CAP-V02"' in package_source
    assert "CAP-V03" not in package_source


def test_e_uses_one_coordinator_execution_without_retry_or_fallback() -> None:
    function = _function(ASSESSMENT, "execute_findings_assessment")
    execute_calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]
    prepare_calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "prepare"
    ]
    assert len(prepare_calls) == 1
    assert len(execute_calls) == 1
    assert not any(isinstance(node, (ast.Try, ast.While)) for node in ast.walk(function))
    assert _calls(E_FILES).isdisjoint(
        {"backoff", "fallback", "replan", "repair", "retry", "sleep"}
    )


def test_e_constructs_signals_but_no_c11_or_canonical_authority_contract() -> None:
    assert "ReviewAssessmentSignal" in _calls((ASSESSMENT,))
    assert "CorrectionHandoffSignal" in _calls((ASSESSMENT,))
    assert _calls(E_FILES).isdisjoint(
        {
            "CorrectionRequest",
            "CorrectionResult",
            "GateDecision",
            "PermissionScope",
            "PromotionPolicy",
            "ValidationResult",
        }
    )
    imports = {module for path in E_FILES for module in _imports(path)}
    assert all("correction_request" not in module for module in imports)
    assert all("correction_result" not in module for module in imports)


def test_e_has_no_ag03_cap_g_cap_a_or_direct_execution_surface() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in E_FILES)
    assert "AG_03" not in source
    assert "CAP-G" not in source
    assert "CAP-A" not in source
    assert "GeneratorAgent" not in source
    assert "GenerationCoordinator" not in source
    assert _attribute_calls(E_FILES).isdisjoint(
        {"correct_production", "execute_correction", "generate", "promote", "validate"}
    )


def test_e_has_no_runtime_or_orchestration_dependency_in_either_direction() -> None:
    imports = {module for path in E_FILES for module in _imports(path)}
    assert all(not module.startswith("backend.agent_runtime.runtime") for module in imports)
    assert all(
        not module.startswith("backend.agent_runtime.orchestration")
        for module in imports
    )
    outer_imports = {
        module
        for root in (RUNTIME, ORCHESTRATION)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all("agents.review" not in module for module in outer_imports)


def test_e_has_no_application_domain_adapter_or_infrastructure_imports() -> None:
    forbidden = ("backend.modules", "backend.adapters", "backend.infrastructure")
    imports = {module for path in E_FILES for module in _imports(path)}
    assert all(not module.startswith(forbidden) for module in imports)


def test_e_has_no_provider_network_sql_vector_or_filesystem_imports() -> None:
    forbidden_roots = {
        "aiohttp",
        "anthropic",
        "asyncio",
        "chromadb",
        "django",
        "fastapi",
        "faiss",
        "google",
        "httpx",
        "langchain",
        "langgraph",
        "openai",
        "pathlib",
        "pinecone",
        "qdrant",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "threading",
        "urllib",
    }
    roots = {
        module.split(".")[0]
        for path in E_FILES
        for module in _imports(path)
    }
    assert roots.isdisjoint(forbidden_roots)


def test_e_adds_no_promotion_validation_persistence_search_or_router() -> None:
    forbidden = {"persist", "promote", "route", "search", "validate"}
    assert _calls(E_FILES).isdisjoint(forbidden)
    assert _attribute_calls(E_FILES).isdisjoint(forbidden)
    class_names = {
        node.name.casefold()
        for path in E_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert all(
        token not in name
        for name in class_names
        for token in ("dispatcher", "handler", "provider", "router", "store")
    )


def test_e_duplicates_no_canonical_review_enum_or_model() -> None:
    expected = {
        "Finding": BACKEND / "agent_runtime" / "contracts" / "review" / "finding.py",
        "ReviewResult": (
            BACKEND / "agent_runtime" / "contracts" / "review" / "review_result.py"
        ),
        "OverallAssessment": (
            BACKEND / "agent_runtime" / "contracts" / "review" / "vocabulary.py"
        ),
        "FindingSeverity": (
            BACKEND / "agent_runtime" / "contracts" / "review" / "vocabulary.py"
        ),
        "ReviewDimension": (
            BACKEND / "agent_runtime" / "contracts" / "review" / "vocabulary.py"
        ),
    }
    assert {name: _class_sites(name) for name in expected} == {
        name: (path,) for name, path in expected.items()
    }


def test_e_has_no_vote_consensus_or_generation_guard_engine() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8").casefold() for path in E_FILES
    )
    assert "vote" not in source
    assert "consensus" not in source
    assert "generationoutputguard" not in source
    assert "evidencesecurityscanner" not in source


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == []
