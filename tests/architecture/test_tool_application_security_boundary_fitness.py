from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
AGENT_RUNTIME = BACKEND / "agent_runtime"


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
    return {
        node.module
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }


def test_authorization_content_and_sandbox_owners_remain_unique() -> None:
    assert len(_definitions("ToolCallPolicy")) == 1
    assert len(_definitions("CapabilityAuthorizationPolicy")) == 1
    assert len(_definitions("UseCaseRouter")) == 1
    assert len(_definitions("InstructionDataBoundaryPolicy")) == 1
    assert len(_definitions("SecurityEvent")) == 1
    assert len(_definitions("SandboxPolicy")) == 1
    assert len(_definitions("StructuredContentSecurityAssessment")) == 1


def test_structural_key_classifier_is_unique_and_reused_by_all_four_boundaries() -> None:
    assert _definitions("StructuralKeyClassifier") == ()
    helper = AGENT_RUNTIME / "security" / "structural_keys.py"
    assert helper.is_file()
    consumers = (
        AGENT_RUNTIME / "security" / "content_isolation.py",
        AGENT_RUNTIME / "policy" / "tool_call_policy.py",
        AGENT_RUNTIME / "tools" / "router.py",
        AGENT_RUNTIME / "application_routing" / "router.py",
        AGENT_RUNTIME / "gates" / "engine.py",
    )
    assert all(
        any("security.structural_keys" in module for module in _imports(path))
        or any(module.endswith("agent_runtime.security") for module in _imports(path))
        for path in consumers
    )


def test_tool_output_has_no_automatic_evidence_conversion_dependency() -> None:
    tool_files = (
        AGENT_RUNTIME / "contracts" / "tools" / "tool_call_result.py",
        AGENT_RUNTIME / "tools" / "router.py",
    )
    imports = {module for path in tool_files for module in _imports(path)}
    assert all("contracts.evidence" not in module for module in imports)
    assert all("agents.evidence" not in module for module in imports)


def test_d_does_not_integrate_agent_handoff_recovery_runtime_or_observability() -> None:
    protected_roots = (
        AGENT_RUNTIME / "contracts" / "delegation",
        AGENT_RUNTIME / "recovery",
        AGENT_RUNTIME / "runtime",
        BACKEND / "infrastructure" / "observability",
    )
    for root in protected_roots:
        for path in _python_files(root):
            assert all("security.tool_application" not in item for item in _imports(path))
            assert all("security.structural_keys" not in item for item in _imports(path))


def test_d_adds_no_secret_scanner_provider_or_runtime_dependency() -> None:
    d_roots = (
        AGENT_RUNTIME / "security",
        AGENT_RUNTIME / "tools",
        AGENT_RUNTIME / "application_routing",
    )
    forbidden_imports = {
        "httpx",
        "openai",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
    }
    imports = {
        module
        for root in d_roots
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all(
        fragment not in module
        for fragment in forbidden_imports
        for module in imports
    )
    assert _definitions("SecretScanner") == ()
    assert _definitions("SecurityEventSink") == ()


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        assert tomllib.load(stream)["project"]["dependencies"] == ["openai>=3.5,<4"]
