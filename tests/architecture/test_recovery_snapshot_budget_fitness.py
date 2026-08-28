from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
RECOVERY = BACKEND / "agent_runtime" / "recovery"
C_FILES = (
    RECOVERY / "budget.py",
    RECOVERY / "budget_ports.py",
    RECOVERY / "snapshot.py",
    RECOVERY / "snapshot_ports.py",
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


def test_canonical_runtime_and_budget_primitives_remain_unique() -> None:
    expected = {
        "RunState": BACKEND / "agent_runtime" / "runtime" / "state" / "run_state.py",
        "StepState": BACKEND / "agent_runtime" / "runtime" / "state" / "step_state.py",
        "BudgetSpec": BACKEND / "agent_runtime" / "contracts" / "policy" / "budget.py",
        "AgentRuntimePolicy": BACKEND / "agent_runtime" / "policy" / "runtime_policy.py",
        "EffectState": (
            BACKEND / "agent_runtime" / "contracts" / "errors" / "error_envelope.py"
        ),
        "EffectLedgerRecord": RECOVERY / "model.py",
    }
    for class_name, path in expected.items():
        assert _defined_classes(BACKEND, class_name) == (path,)


def test_c_reuses_canonical_types_instead_of_shadowing_them() -> None:
    imports = _imports(C_FILES)

    assert "backend.agent_runtime.contracts" in imports
    assert "backend.agent_runtime.policy" in imports
    assert "backend.agent_runtime.recovery.model" in imports
    assert "backend.agent_runtime.runtime.state" in imports
    assert "backend.shared_kernel.time" in imports


def test_c_has_no_provider_network_database_filesystem_or_process_io() -> None:
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
    roots = {module.split(".")[0] for module in _imports(C_FILES)}

    assert roots.isdisjoint(forbidden_roots)


def test_c_has_no_execution_gate_or_orchestration_dependency() -> None:
    forbidden_fragments = {
        "agent_runtime.application_routing",
        "agent_runtime.gates",
        "agent_runtime.orchestration",
        "agent_runtime.runtime.execution",
        "agent_runtime.runtime.scheduling",
        "agent_runtime.tools",
    }
    imports = _imports(C_FILES)

    assert all(
        fragment not in module
        for fragment in forbidden_fragments
        for module in imports
    )


def test_c_does_not_introduce_later_phase_engines_or_controls() -> None:
    forbidden_classes = {
        "ApplicationEffectProbePort",
        "Backoff",
        "BackoffPolicy",
        "CircuitBreaker",
        "CircuitBreakerPolicy",
        "EffectReconciliationEngine",
        "RecoveryCoordinator",
        "ReplayGuard",
        "RetryPolicy",
        "ToolEffectProbePort",
    }
    defined = {
        node.name
        for path in C_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }

    assert defined.isdisjoint(forbidden_classes)


def test_budget_and_snapshot_stores_are_protocols_only_in_production() -> None:
    expected = {
        RECOVERY / "budget_ports.py": {"BudgetStatePort"},
        RECOVERY / "snapshot_ports.py": {"StateSnapshotStorePort"},
    }
    for path, names in expected.items():
        protocols = {
            node.name
            for node in _tree(path).body
            if isinstance(node, ast.ClassDef)
            and any(
                isinstance(base, ast.Name) and base.id == "Protocol"
                for base in node.bases
            )
        }
        assert protocols == names
    production_source = "\n".join(path.read_text(encoding="utf-8") for path in C_FILES)
    assert "InMemory" not in production_source


def test_c_contains_no_sleep_retry_replay_dynamic_execution_or_background_loop() -> None:
    forbidden_calls = {"create_task", "eval", "exec", "replay", "retry", "sleep"}
    for path in C_FILES:
        tree = _tree(path)
        assert not any(isinstance(node, (ast.While, ast.AsyncFor)) for node in ast.walk(tree))
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert called.isdisjoint(forbidden_calls)


def test_budget_vocabulary_does_not_claim_permission_authority() -> None:
    forbidden_members = {"ALLOW", "APPROVED", "DELEGATE", "PROMOTE", "REQUEST"}
    enum_members = {
        node.targets[0].id
        for path in C_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }

    assert enum_members.isdisjoint(forbidden_members)


def test_project_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]

    assert project["dependencies"] == ["openai>=3.5,<4"]
