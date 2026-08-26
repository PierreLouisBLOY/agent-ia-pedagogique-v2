from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
RECOVERY = BACKEND / "agent_runtime" / "recovery"
D_FILES = (
    RECOVERY / "reconciliation.py",
    RECOVERY / "reconciliation_engine.py",
    RECOVERY / "reconciliation_ports.py",
)


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


def _imports(paths: tuple[Path, ...]) -> set[str]:
    modules: set[str] = set()
    for path in paths:
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
            elif isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
    return modules


def test_d_reuses_effect_state_status_record_and_ledger_port() -> None:
    assert _defined_classes(BACKEND, "EffectState") == (
        BACKEND / "agent_runtime" / "contracts" / "errors" / "error_envelope.py",
    )
    assert _defined_classes(BACKEND, "ReconciliationStatus") == (
        RECOVERY / "model.py",
    )
    assert _defined_classes(BACKEND, "EffectLedgerRecord") == (
        RECOVERY / "model.py",
    )
    assert _defined_classes(BACKEND, "EffectLedgerPort") == (
        RECOVERY / "ports.py",
    )


def test_exactly_one_reconciliation_engine_is_defined() -> None:
    assert _defined_classes(BACKEND, "EffectReconciliationEngine") == (
        RECOVERY / "reconciliation_engine.py",
    )


def test_two_typed_probe_protocols_exist_without_generic_probe() -> None:
    ports = _tree(RECOVERY / "reconciliation_ports.py")
    protocols = {
        node.name
        for node in ports.body
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(base, ast.Name) and base.id == "Protocol" for base in node.bases
        )
    }

    assert protocols == {"ToolEffectProbePort", "ApplicationEffectProbePort"}
    assert "EffectProbePort" not in protocols


def test_d_has_no_provider_network_database_filesystem_or_process_io() -> None:
    forbidden_roots = {
        "asyncio",
        "httpx",
        "os",
        "pathlib",
        "pickle",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "threading",
        "time",
        "urllib",
    }
    roots = {module.split(".")[0] for module in _imports(D_FILES)}

    assert roots.isdisjoint(forbidden_roots)


def test_d_has_no_tool_application_execution_or_orchestration_dependency() -> None:
    forbidden_fragments = {
        "agent_runtime.application_routing",
        "agent_runtime.gates",
        "agent_runtime.orchestration",
        "agent_runtime.runtime.execution",
        "agent_runtime.runtime.routing",
        "agent_runtime.tools",
    }
    imports = _imports(D_FILES)

    assert all(
        fragment not in module
        for fragment in forbidden_fragments
        for module in imports
    )


def test_d_defines_no_concrete_probe_adapter_or_later_phase_control() -> None:
    forbidden_classes = {
        "Backoff",
        "BackoffPolicy",
        "CircuitBreaker",
        "CircuitBreakerPolicy",
        "ReplayGuard",
        "RetryPolicy",
    }
    defined = {
        node.name
        for path in D_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }
    source = "\n".join(path.read_text(encoding="utf-8") for path in D_FILES)

    assert defined.isdisjoint(forbidden_classes)
    assert "Adapter" not in source
    assert "InMemory" not in source


def test_d_contains_no_polling_retry_replay_sleep_or_dynamic_execution() -> None:
    forbidden_calls = {"create_task", "eval", "exec", "replay", "retry", "sleep"}
    for path in D_FILES:
        tree = _tree(path)
        assert not any(isinstance(node, (ast.While, ast.AsyncFor)) for node in ast.walk(tree))
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert called.isdisjoint(forbidden_calls)


def test_reconciliation_vocabulary_has_no_execution_authority() -> None:
    forbidden_members = {
        "ALLOW",
        "ALLOW_RETRY",
        "APPROVED",
        "DELEGATE",
        "PROMOTE",
        "REPLAY",
        "REQUEST",
        "RETRY",
    }
    enum_members = {
        node.targets[0].id
        for path in D_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }

    assert enum_members.isdisjoint(forbidden_members)


def test_project_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]

    assert project["dependencies"] == []
