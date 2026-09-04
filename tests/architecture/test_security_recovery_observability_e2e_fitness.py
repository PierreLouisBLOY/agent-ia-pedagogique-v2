from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
TRANSVERSE = ROOT / "tests" / "e2e" / "core" / "transverse_adapters.py"


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            values.append(node.module)
    return tuple(values)


def test_backend_never_imports_phase_f_transverse_bindings() -> None:
    offenders = tuple(
        path.relative_to(ROOT).as_posix()
        for path in _python_files(BACKEND)
        if any("tests.e2e.core.transverse" in name for name in _imports(path))
    )
    assert offenders == ()


def test_observability_package_does_not_depend_on_gate_or_application_promotion() -> None:
    observability = BACKEND / "agent_runtime" / "observability"
    forbidden = (
        "backend.agent_runtime.gates",
        "backend.agent_runtime.application_routing",
    )
    offenders = tuple(
        path.relative_to(ROOT).as_posix()
        for path in _python_files(observability)
        if any(name.startswith(forbidden) for name in _imports(path))
    )
    assert offenders == ()


def test_agent_packages_do_not_construct_gate_decisions() -> None:
    agents = BACKEND / "agent_runtime" / "agents"
    offenders = tuple(
        path.relative_to(ROOT).as_posix()
        for path in _python_files(agents)
        if "GateDecision(" in path.read_text(encoding="utf-8")
    )
    assert offenders == ()


def test_recovery_package_has_no_permission_or_gate_decision_constructors() -> None:
    recovery = BACKEND / "agent_runtime" / "recovery"
    offenders = tuple(
        path.relative_to(ROOT).as_posix()
        for path in _python_files(recovery)
        if any(
            marker in path.read_text(encoding="utf-8")
            for marker in ("PermissionScope(", "GateDecision(")
        )
    )
    assert offenders == ()


def test_later_provider_work_preserves_phase_f_backend_owners() -> None:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "backend"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    changed = tuple(line for line in result.stdout.splitlines() if line)
    allowed = (
        "backend/adapters/outbound/",
        "backend/infrastructure/composition/factories/",
        "backend/infrastructure/config/",
    )
    f2a_retrieval_files = {
        "backend/agent_runtime/agents/evidence/__init__.py",
        "backend/agent_runtime/agents/evidence/evidence_agent_model.py",
        "backend/agent_runtime/agents/evidence/retrieval_coordination_model.py",
        "backend/agent_runtime/agents/evidence/retrieval_coordinator.py",
        "backend/agent_runtime/agents/evidence/retrieval_ports.py",
    }
    b02_local_boundary_files = {
        "backend/agent_runtime/sandbox/ports.py",
        "backend/infrastructure/filesystem/__init__.py",
        "backend/infrastructure/filesystem/security.py",
    }
    assert all(
        path.startswith(allowed)
        or path in f2a_retrieval_files
        or path in b02_local_boundary_files
        for path in changed
    )


def test_phase_f_binding_is_provider_network_and_runtime_storage_free() -> None:
    imports = _imports(TRANSVERSE)
    forbidden_imports = ("requests", "httpx", "urllib", "socket", "sqlite3")
    assert not any(name.startswith(forbidden_imports) for name in imports)
    source = TRANSVERSE.read_text(encoding="utf-8")
    assert "open(" not in source
    assert "GateDecision(" not in source


def test_phase_f_does_not_add_capability_workflow_agent_or_golden_case() -> None:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--unified=0",
            "HEAD",
            "--",
            "backend/agent_runtime/registry",
            "backend/agent_runtime/orchestration/workflows",
            "tests/e2e/core/catalog.py",
            "tests/e2e/core/expectations.py",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""
