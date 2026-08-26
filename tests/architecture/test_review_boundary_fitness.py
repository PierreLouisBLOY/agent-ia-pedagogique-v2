from __future__ import annotations

import ast
import inspect
import tomllib
from pathlib import Path

from backend.agent_runtime.agents.review import ReviewPort

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
REVIEW = BACKEND / "agent_runtime" / "agents" / "review"
RUNTIME = BACKEND / "agent_runtime" / "runtime"
ORCHESTRATION = BACKEND / "agent_runtime" / "orchestration"
MODEL = REVIEW / "review_model.py"
PORTS = REVIEW / "review_ports.py"
BOUNDARY_FILES = (MODEL, PORTS)


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


def _class_sites(name: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _python_files(BACKEND)
        if any(
            isinstance(node, ast.ClassDef) and node.name == name
            for node in ast.walk(_tree(path))
        )
    )


def test_review_package_contains_only_the_provider_neutral_boundary() -> None:
    assert REVIEW.is_dir()
    assert {path.name for path in _python_files(REVIEW)} == {
        "__init__.py",
        "review_agent.py",
        "review_agent_model.py",
        "review_coordination_model.py",
        "review_coordinator.py",
        "review_model.py",
        "review_ports.py",
    }


def test_review_port_is_unique_and_has_one_outbound_method() -> None:
    assert _class_sites("ReviewPort") == (PORTS,)
    assert getattr(ReviewPort, "_is_protocol", False)
    assert getattr(ReviewPort, "_is_runtime_protocol", False)
    assert tuple(inspect.signature(ReviewPort.review).parameters) == (
        "self",
        "request",
    )
    public_methods = {
        name
        for name, value in ReviewPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert public_methods == {"review"}


def test_review_boundary_creates_no_agent_or_provider() -> None:
    class_names = {
        node.name
        for path in _python_files(REVIEW)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert all("Provider" not in name for name in class_names)
    assert all("Handler" not in name for name in class_names)
    assert all("Dispatcher" not in name for name in class_names)


def test_review_and_runtime_orchestration_do_not_import_each_other() -> None:
    review_imports = {
        module for path in _python_files(REVIEW) for module in _imports(path)
    }
    assert all(
        not module.startswith("backend.agent_runtime.runtime")
        for module in review_imports
    )
    assert all(
        not module.startswith("backend.agent_runtime.orchestration")
        for module in review_imports
    )
    outer_imports = {
        module
        for root in (RUNTIME, ORCHESTRATION)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all(
        not module.startswith("backend.agent_runtime.agents.review")
        for module in outer_imports
    )


def test_review_boundary_has_no_modules_adapters_or_infrastructure_imports() -> None:
    forbidden = ("backend.modules", "backend.adapters", "backend.infrastructure")
    imports = {module for path in _python_files(REVIEW) for module in _imports(path)}
    assert all(not module.startswith(forbidden) for module in imports)


def test_review_boundary_has_no_provider_network_sql_vector_or_filesystem_imports() -> None:
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
        "multiprocessing",
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
    imported_roots = {
        module.split(".")[0]
        for path in _python_files(REVIEW)
        for module in _imports(path)
    }
    assert imported_roots.isdisjoint(forbidden_roots)


def test_review_boundary_has_no_io_network_retry_or_loop_surface() -> None:
    attribute_calls = {
        node.func.attr
        for path in BOUNDARY_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert attribute_calls.isdisjoint(
        {
            "connect",
            "execute",
            "get",
            "open",
            "post",
            "read_bytes",
            "read_text",
            "request",
            "retry",
            "sleep",
            "urlopen",
            "write_bytes",
            "write_text",
        }
    )
    assert not any(
        isinstance(node, ast.While)
        for path in _python_files(REVIEW)
        for node in ast.walk(_tree(path))
    )


def test_review_boundary_does_not_reuse_other_agent_security_engines() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(REVIEW))
    assert "GenerationOutputGuard" not in source
    assert "EvidenceSecurityScanner" not in source
    imports = {module for path in _python_files(REVIEW) for module in _imports(path)}
    assert all("agents.generation" not in module for module in imports)
    assert all("agents.evidence" not in module for module in imports)


def test_review_boundary_does_not_duplicate_canonical_review_models_or_enums() -> None:
    expected = {
        "ReviewResult": BACKEND / "agent_runtime" / "contracts" / "review" / "review_result.py",
        "Finding": BACKEND / "agent_runtime" / "contracts" / "review" / "finding.py",
        "FindingSeverity": BACKEND / "agent_runtime" / "contracts" / "review" / "vocabulary.py",
        "ReviewDimension": BACKEND / "agent_runtime" / "contracts" / "review" / "vocabulary.py",
        "OverallAssessment": BACKEND / "agent_runtime" / "contracts" / "review" / "vocabulary.py",
    }
    assert {name: _class_sites(name) for name in expected} == {
        name: (path,) for name, path in expected.items()
    }
    calls = {
        node.func.id
        for path in BOUNDARY_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert calls.isdisjoint(
        {"CorrectionRequest", "Finding", "ReviewRequest", "ReviewResult"}
    )


def test_review_boundary_does_not_import_registry_or_workflow_mutation_surfaces() -> None:
    imports = {module for path in _python_files(REVIEW) for module in _imports(path)}
    assert all("agent_runtime.registry" not in module for module in imports)
    assert all("orchestration.workflows" not in module for module in imports)
    assert all("agent_runtime.runtime" not in module for module in imports)


def test_review_port_has_no_production_implementation() -> None:
    classes = {
        node.name: tuple(base.id for base in node.bases if isinstance(base, ast.Name))
        for path in _python_files(REVIEW)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert classes["ReviewPort"] == ("Protocol",)
    assert all(
        "ReviewPort" not in bases
        for name, bases in classes.items()
        if name != "ReviewPort"
    )


def test_review_boundary_contains_no_provider_prompt_or_authority_service() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in _python_files(REVIEW)
    )
    assert all(
        token not in source
        for token in (
            "api_key",
            "endpoint_url",
            "gpt-",
            "claude-",
            "gemini-",
            "prompt_template",
            "provider_response",
        )
    )


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == []
