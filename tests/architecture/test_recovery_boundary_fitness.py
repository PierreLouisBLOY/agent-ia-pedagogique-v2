from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
RECOVERY = BACKEND / "agent_runtime" / "recovery"
IDEMPOTENCY_BOUNDARY = (
    RECOVERY / "model.py",
    RECOVERY / "idempotency.py",
    RECOVERY / "ports.py",
)


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _defined_classes(root: Path, class_name: str) -> tuple[Path, ...]:
    matches: list[Path] = []
    for path in _python_files(root):
        if any(
            isinstance(node, ast.ClassDef) and node.name == class_name
            for node in ast.walk(_tree(path))
        ):
            matches.append(path)
    return tuple(matches)


def _import_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_effect_state_and_error_envelope_remain_unique() -> None:
    assert _defined_classes(BACKEND, "EffectState") == (
        BACKEND / "agent_runtime" / "contracts" / "errors" / "error_envelope.py",
    )
    assert _defined_classes(BACKEND, "ErrorEnvelope") == (
        BACKEND / "agent_runtime" / "contracts" / "errors" / "error_envelope.py",
    )


def test_recovery_has_no_provider_io_database_or_concurrency_dependency() -> None:
    forbidden_roots = {
        "asyncio",
        "httpx",
        "os",
        "pathlib",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "threading",
        "time",
        "urllib",
    }
    for path in _python_files(RECOVERY):
        assert _import_roots(path).isdisjoint(forbidden_roots)


def test_recovery_does_not_depend_on_execution_authority_boundaries() -> None:
    forbidden_fragments = {
        "agent_runtime.application_routing",
        "agent_runtime.gates",
        "agent_runtime.orchestration.coordination",
        "agent_runtime.runtime.execution",
        "agent_runtime.tools",
    }
    imports: set[str] = set()
    for path in _python_files(RECOVERY):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
            elif isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
    assert all(
        fragment not in module
        for fragment in forbidden_fragments
        for module in imports
    )


def test_b_does_not_introduce_later_phase_components() -> None:
    forbidden_classes = {
        "BackoffPolicy",
        "BudgetState",
        "CircuitBreaker",
        "CircuitBreakerPolicy",
        "EffectReconciliationEngine",
        "RecoveryCoordinator",
        "ReplayGuard",
        "RetryPolicy",
        "StateSnapshot",
        "StateSnapshotStore",
        "ToolEffectProbePort",
        "ApplicationEffectProbePort",
    }
    defined = {
        node.name
        for path in IDEMPOTENCY_BOUNDARY
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    assert defined.isdisjoint(forbidden_classes)


def test_recovery_contains_no_retry_replay_sleep_or_background_loop() -> None:
    forbidden_calls = {"retry", "replay", "sleep", "create_task"}
    for path in _python_files(RECOVERY):
        tree = _tree(path)
        assert not any(isinstance(node, (ast.While, ast.AsyncFor)) for node in ast.walk(tree))
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert called.isdisjoint(forbidden_calls)


def test_effect_ledger_is_only_a_protocol_in_production() -> None:
    ports = _tree(RECOVERY / "ports.py")
    protocols = {
        node.name
        for node in ports.body
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(base, ast.Name) and base.id == "Protocol" for base in node.bases
        )
    }
    assert protocols == {"EffectLedgerPort"}
    assert "InMemory" not in "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(RECOVERY)
    )


def test_project_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["dependencies"] == []
