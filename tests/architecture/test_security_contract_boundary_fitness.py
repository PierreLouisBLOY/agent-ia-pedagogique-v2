from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SECURITY_CONTRACTS = BACKEND / "agent_runtime" / "contracts" / "security"


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _defined_classes(root: Path, class_name: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _python_files(root)
        if any(
            isinstance(node, ast.ClassDef) and node.name == class_name
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


def test_security_contracts_are_unique_and_live_in_the_agent_contract_boundary() -> None:
    assert _defined_classes(BACKEND, "ContentTrustLabel") == (
        SECURITY_CONTRACTS / "trust.py",
    )
    assert _defined_classes(BACKEND, "SecurityEvent") == (
        SECURITY_CONTRACTS / "security_event.py",
    )
    for name in (
        "ContentOrigin",
        "ContentRole",
        "ContentTrustClass",
        "SecurityBoundary",
        "SecurityEventType",
        "SecuritySeverity",
    ):
        assert len(_defined_classes(BACKEND, name)) == 1
    assert not (BACKEND / "shared_kernel" / "security").exists()
    assert not (SECURITY_CONTRACTS / "observability.py").exists()


def test_security_contracts_have_no_provider_io_or_observability_dependency() -> None:
    forbidden_fragments = {
        "agent_runtime.adapters",
        "agent_runtime.observability",
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
        for path in _python_files(SECURITY_CONTRACTS)
        for module in _imports(path)
    }

    assert all(
        fragment not in module
        for fragment in forbidden_fragments
        for module in imports
    )


def test_security_contracts_define_no_policy_guard_engine_or_authority_decision() -> None:
    forbidden_classes = {
        "EventBus",
        "InjectionDetector",
        "SecurityEventExporter",
        "SecurityEventLogger",
        "SecurityEventPublisher",
        "SecurityEventSink",
        "SecurityMiddleware",
        "SecurityPolicy",
        "SecurityGuard",
        "SecurityEngine",
        "SecurityDecision",
        "SecurityRouter",
    }
    defined = {
        node.name
        for path in _python_files(SECURITY_CONTRACTS)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    enum_values = {
        node.value.value
        for path in _python_files(SECURITY_CONTRACTS)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }

    assert defined.isdisjoint(forbidden_classes)
    assert enum_values.isdisjoint({"ALLOW", "REQUEST", "DELEGATE", "APPROVED", "PROMOTE"})


def test_security_contracts_are_integrated_only_into_content_boundaries() -> None:
    protected_roots = (
        BACKEND / "agent_runtime" / "gates",
        BACKEND / "agent_runtime" / "recovery",
        BACKEND / "agent_runtime" / "sandbox",
        BACKEND / "agent_runtime" / "tools",
    )
    for root in protected_roots:
        for path in _python_files(root):
            assert all("contracts.security" not in module for module in _imports(path))

    allowed_exports = {
        SECURITY_CONTRACTS / "__init__.py",
        SECURITY_CONTRACTS / "content.py",
        SECURITY_CONTRACTS / "security_event.py",
        SECURITY_CONTRACTS / "trust.py",
        BACKEND / "agent_runtime" / "contracts" / "__init__.py",
    }
    content_boundary_integrations = {
        BACKEND / "agent_runtime" / "contracts" / "evidence" / "labeled_evidence.py",
        BACKEND / "agent_runtime" / "security" / "content_isolation.py",
        BACKEND / "agent_runtime" / "agents" / "evidence" / "evidence_expansion_model.py",
        BACKEND / "agent_runtime" / "agents" / "evidence" / "evidence_security.py",
        BACKEND / "agent_runtime" / "agents" / "evidence" / "evidence_security_model.py",
        BACKEND / "agent_runtime" / "agents" / "generation" / "generation_guard.py",
        BACKEND / "agent_runtime" / "agents" / "generation" / "generation_guard_model.py",
        BACKEND / "agent_runtime" / "agents" / "generation" / "generation_model.py",
        BACKEND / "agent_runtime" / "agents" / "review" / "review_assessment_model.py",
        BACKEND / "agent_runtime" / "agents" / "review" / "review_coordination_model.py",
        BACKEND / "agent_runtime" / "agents" / "review" / "review_security.py",
        BACKEND / "agent_runtime" / "agents" / "review" / "review_security_model.py",
    }
    for path in _python_files(BACKEND):
        if path in allowed_exports | content_boundary_integrations:
            continue
        assert all("contracts.security" not in module for module in _imports(path))


def test_security_event_has_no_free_text_or_raw_content_field() -> None:
    tree = _tree(SECURITY_CONTRACTS / "security_event.py")
    event = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SecurityEvent"
    )
    fields = {
        node.target.id
        for node in event.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }

    assert fields.isdisjoint(
        {
            "message",
            "summary",
            "description",
            "prompt",
            "document",
            "payload",
            "idempotency_key",
            "authority",
            "decision",
        }
    )


def test_project_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["dependencies"] == []
