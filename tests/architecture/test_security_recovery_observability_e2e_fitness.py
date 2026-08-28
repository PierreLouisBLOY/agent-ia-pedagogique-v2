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


def test_phase_f_adds_no_backend_production_delta() -> None:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "backend"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == ""


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
