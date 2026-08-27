from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OBSERVABILITY = BACKEND / "agent_runtime" / "observability"
INFRA = BACKEND / "infrastructure" / "observability"
WRAPPERS = OBSERVABILITY / "runtime_wrappers.py"
EMITTER = OBSERVABILITY / "runtime_emitter.py"
CONTEXT = OBSERVABILITY / "runtime_context.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_runtime_integration_is_explicit_composition_without_core_import_reversal() -> None:
    protected = (
        BACKEND / "agent_runtime" / "runtime",
        BACKEND / "agent_runtime" / "recovery",
        BACKEND / "agent_runtime" / "orchestration",
        BACKEND / "agent_runtime" / "tools",
        BACKEND / "agent_runtime" / "application_routing",
        BACKEND / "agent_runtime" / "gates",
    )
    for root in protected:
        for path in root.rglob("*.py"):
            assert all(
                "infrastructure.observability" not in module
                and "runtime_observability" not in module
                for module in _imports(path)
            )
    assert all(
        not module.startswith("backend.infrastructure")
        for path in (WRAPPERS, EMITTER, CONTEXT)
        for module in _imports(path)
    )


def test_wrappers_do_not_recall_business_sources_or_own_authority() -> None:
    text = WRAPPERS.read_text(encoding="utf-8")
    forbidden_calls = (
        ".schedule(",
        ".resolve_tool_input(",
        ".resolve_use_case_input(",
        ".resolve_agent_input(",
        ".route(",
        ".evaluate(",
        ".reconcile(",
        ".compare_and_set(",
        ".flush(",
    )
    forbidden_owners = (
        "ToolCallPolicy",
        "GateEngine",
        "RetryPolicy(",
        "ReplayGuard(",
        "SecurityRuntimeGuard",
        "EffectState",
    )
    assert all(fragment not in text for fragment in forbidden_calls)
    assert all(fragment not in text for fragment in forbidden_owners)
    assert "self.inner.check(" in text
    assert "self.inner.run(" in text
    assert "self.inner.execute_cycle(" in text
    assert "RecoveryCoordinator.recover(" in text


def test_trace_sidecar_never_reads_legacy_maps_or_business_payloads() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (WRAPPERS, EMITTER, CONTEXT)
    )
    for forbidden in (
        "trace_flags",
        "DelegationEnvelope",
        ".arguments",
        ".payload",
        ".requested_effect",
        ".output",
        ".metrics.items",
        "correlation_id.value",
        "run_id.encode",
    ):
        assert forbidden not in text


def test_context_is_sidecar_only_and_absent_from_runtime_and_snapshot_state() -> None:
    context_text = CONTEXT.read_text(encoding="utf-8")
    run_state = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            BACKEND / "agent_runtime" / "runtime" / "state" / "run_state.py",
            BACKEND / "agent_runtime" / "runtime" / "state" / "step_state.py",
        )
    )
    snapshot = (
        BACKEND / "agent_runtime" / "recovery" / "snapshot.py"
    ).read_text(encoding="utf-8")
    assert "RuntimeObservabilityContext" in context_text
    assert "RuntimeObservabilityContext" not in run_state
    assert "RuntimeObservabilityContext" not in snapshot
    for forbidden in (
        "SpanRecord",
        "StructuredLogRecord",
        "MetricPoint",
        "DeliveryAttempt",
    ):
        assert forbidden not in run_state
        assert forbidden not in snapshot


def test_g_adds_no_global_telemetry_durability_or_external_provider() -> None:
    g_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            CONTEXT,
            EMITTER,
            WRAPPERS,
            OBSERVABILITY / "noop.py",
            INFRA / "providers.py",
        )
    )
    imports = {
        module
        for path in (
            CONTEXT,
            EMITTER,
            WRAPPERS,
            OBSERVABILITY / "noop.py",
            INFRA / "providers.py",
        )
        for module in _imports(path)
    }
    forbidden_imports = {
        "contextvars",
        "logging",
        "sqlite3",
        "sqlalchemy",
        "opentelemetry",
        "prometheus_client",
    }
    assert imports.isdisjoint(forbidden_imports)
    for forbidden in (
        "ContextVar",
        "GlobalLogger",
        "GlobalTracer",
        "GlobalTelemetryManager",
        "singleton",
        "SQLite",
        "WAL",
        "telemetry ledger",
        "open(",
    ):
        assert forbidden not in g_text


def test_delivery_remains_submit_only_and_dependencies_stay_empty() -> None:
    assert ".flush(" not in EMITTER.read_text(encoding="utf-8")
    assert ".flush(" not in WRAPPERS.read_text(encoding="utf-8")
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["dependencies"] == []
