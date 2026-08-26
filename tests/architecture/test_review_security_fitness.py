from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
REVIEW = BACKEND / "agent_runtime" / "agents" / "review"
SECURITY = REVIEW / "review_security.py"
SECURITY_MODEL = REVIEW / "review_security_model.py"
F_FILES = (SECURITY, SECURITY_MODEL)
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


def _class_sites(name: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _python_files(BACKEND)
        if any(
            isinstance(node, ast.ClassDef) and node.name == name
            for node in ast.walk(_tree(path))
        )
    )


def _call_names(paths: tuple[Path, ...]) -> set[str]:
    names: set[str] = set()
    for path in paths:
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def test_f_adds_one_pure_review_security_guard_and_keeps_core_surfaces_unique() -> None:
    assert all(path.is_file() and path.parent == REVIEW for path in F_FILES)
    assert _class_sites("ReviewSecurityGuard") == (SECURITY,)
    assert _class_sites("ReviewerAgent") == (REVIEW / "review_agent.py",)
    assert _class_sites("ReviewCoordinator") == (REVIEW / "review_coordinator.py",)
    assert _class_sites("ReviewPort") == (REVIEW / "review_ports.py",)


def test_review_security_reuses_evidence_models_but_not_evidence_scanner() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in F_FILES)
    assert "EvidenceSecurityAssessment" in source
    assert "EvidenceSecuritySignalCode" in source
    assert "class EvidenceSecurityAssessment" not in source
    assert "class EvidenceSecuritySignalCode" not in source
    assert "EvidenceSecurityScanner" not in source


def test_review_security_does_not_use_generation_guard_or_generation_authority() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in F_FILES)
    assert "GenerationOutputGuard" not in source
    assert "GenerationCoordinator" not in source
    assert "GeneratorAgent" not in source
    assert all("agents.generation" not in module for path in F_FILES for module in _imports(path))


def test_review_security_has_no_runtime_or_orchestration_dependency_in_either_direction() -> None:
    imports = {module for path in F_FILES for module in _imports(path)}
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


def test_review_security_imports_no_provider_network_sql_vector_or_filesystem() -> None:
    forbidden_roots = {
        "aiohttp",
        "anthropic",
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
        "urllib",
    }
    roots = {
        module.split(".")[0]
        for path in F_FILES
        for module in _imports(path)
    }
    assert roots.isdisjoint(forbidden_roots)


def test_review_security_performs_no_io_url_following_or_tool_execution() -> None:
    forbidden_calls = {
        "connect",
        "download",
        "eval",
        "exec",
        "fetch",
        "open",
        "read_text",
        "request",
        "run",
        "system",
        "urlopen",
        "write_text",
    }
    assert _call_names(F_FILES).isdisjoint(forbidden_calls)
    source = "\n".join(
        path.read_text(encoding="utf-8").casefold() for path in F_FILES
    )
    assert "links_followed=true" not in source.replace(" ", "")
    assert "external_actions_allowed=true" not in source.replace(" ", "")


def test_review_security_constructs_no_promotion_gate_c11_or_ag03_surface() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in F_FILES)
    forbidden = {
        "CorrectionRequest",
        "GateDecision",
        "PermissionScope",
        "PromotionPolicy",
        "ValidationResult",
    }
    assert forbidden.isdisjoint(_call_names(F_FILES))
    assert "AG_03" not in source
    assert "CAP-G" not in source
    assert "CAP-A" not in source


def test_review_security_adds_no_canonical_review_enum_duplicate() -> None:
    canonical = {
        "FindingSeverity": (
            BACKEND / "agent_runtime" / "contracts" / "review" / "vocabulary.py"
        ),
        "OverallAssessment": (
            BACKEND / "agent_runtime" / "contracts" / "review" / "vocabulary.py"
        ),
        "ReviewDimension": (
            BACKEND / "agent_runtime" / "contracts" / "review" / "vocabulary.py"
        ),
    }
    assert {name: _class_sites(name) for name in canonical} == {
        name: (path,) for name, path in canonical.items()
    }
    assert _class_sites("ReviewSecurityDisposition") == (SECURITY_MODEL,)


def test_review_security_is_stateless_and_has_no_mutating_public_authority_method() -> None:
    guard = next(
        node
        for node in ast.walk(_tree(SECURITY))
        if isinstance(node, ast.ClassDef) and node.name == "ReviewSecurityGuard"
    )
    public_methods = {
        node.name
        for node in guard.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    }
    assert public_methods == {"assess"}
    assert public_methods.isdisjoint(
        {"approve", "execute", "follow", "promote", "validate"}
    )


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == []
