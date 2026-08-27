from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CONTRACT_SECURITY = BACKEND / "agent_runtime" / "contracts" / "security"
CONTENT_SECURITY = BACKEND / "agent_runtime" / "security"


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _definitions(name: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _python_files(BACKEND)
        if any(
            isinstance(node, ast.ClassDef) and node.name == name
            for node in ast.walk(_tree(path))
        )
    )


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_common_vocabulary_and_content_policy_are_unique() -> None:
    assert _definitions("ContentThreatSignalCode") == (CONTRACT_SECURITY / "content.py",)
    assert _definitions("ContentThreatSignal") == (CONTRACT_SECURITY / "content.py",)
    assert _definitions("InstructionDataBoundaryPolicy") == (
        CONTENT_SECURITY / "content_isolation.py",
    )
    assert _definitions("ContentTrustLabel") == (CONTRACT_SECURITY / "trust.py",)
    assert _definitions("SecurityEvent") == (CONTRACT_SECURITY / "security_event.py",)


def test_domain_specific_owners_remain_distinct() -> None:
    assert _definitions("EvidenceSecuritySignalCode") == (
        BACKEND
        / "agent_runtime"
        / "agents"
        / "evidence"
        / "evidence_security_model.py",
    )
    assert _definitions("GenerationOutputGuard") == (
        BACKEND / "agent_runtime" / "agents" / "generation" / "generation_guard.py",
    )
    assert _definitions("ReviewSecurityGuard") == (
        BACKEND / "agent_runtime" / "agents" / "review" / "review_security.py",
    )


def test_evidence_provenance_quality_codes_remain_local() -> None:
    source = (
        BACKEND
        / "agent_runtime"
        / "agents"
        / "evidence"
        / "evidence_security_model.py"
    ).read_text(encoding="utf-8")
    for name in (
        "DUPLICATE_CORROBORATION",
        "CROSS_SOURCE_DUPLICATE_CONTENT",
        "VERSION_DIVERGENCE",
        "SOURCE_REPORTED_STALE",
    ):
        assert name in source
        assert name not in (CONTRACT_SECURITY / "content.py").read_text(encoding="utf-8")


def test_content_security_has_no_io_provider_observability_or_secret_scanner() -> None:
    forbidden_imports = {
        "asyncio",
        "backend.adapters",
        "backend.infrastructure",
        "httpx",
        "logging",
        "os",
        "pathlib",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "urllib",
    }
    imports = {
        module
        for root in (CONTRACT_SECURITY, CONTENT_SECURITY)
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all(
        fragment not in module
        for fragment in forbidden_imports
        for module in imports
    )
    defined = {
        node.name
        for root in (CONTRACT_SECURITY, CONTENT_SECURITY)
        for path in _python_files(root)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert defined.isdisjoint(
        {
            "SecretScanner",
            "SecretValueScanner",
            "SecurityEventSink",
            "SecurityLogger",
            "SecurityExporter",
            "ToolSecurityPolicy",
            "ApplicationSecurityPolicy",
        }
    )


def test_d_integrates_content_security_without_touching_recovery_or_delegation() -> None:
    protected_roots = (
        BACKEND / "agent_runtime" / "recovery",
        BACKEND / "agent_runtime" / "contracts" / "delegation",
    )
    for root in protected_roots:
        for path in _python_files(root):
            assert all("agent_runtime.security" not in module for module in _imports(path))
    integrated_roots = (
        BACKEND / "agent_runtime" / "application_routing",
        BACKEND / "agent_runtime" / "tools",
    )
    assert any(
        "agent_runtime.security" in module
        for root in integrated_roots
        for path in _python_files(root)
        for module in _imports(path)
    )


def test_project_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["dependencies"] == []
