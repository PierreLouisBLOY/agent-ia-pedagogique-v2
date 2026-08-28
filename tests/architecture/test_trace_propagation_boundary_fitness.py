from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OBSERVABILITY = BACKEND / "agent_runtime" / "observability"
TRACE_POLICY = OBSERVABILITY / "trace_policy.py"
SPAN_CATALOG = OBSERVABILITY / "span_catalog.py"
SPAN_FACTORY = OBSERVABILITY / "span_factory.py"
TRACE_CONTRACT = (
    BACKEND / "agent_runtime" / "contracts" / "observability" / "trace.py"
)


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _fields(path: Path, class_name: str) -> set[str]:
    target = next(
        node
        for node in _tree(path).body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return {
        node.target.id
        for node in target.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }


def test_trace_policy_is_pure_explicit_passing_without_global_provider() -> None:
    text = TRACE_POLICY.read_text(encoding="utf-8")
    imports = _imports(TRACE_POLICY)
    forbidden_imports = {
        "contextvars",
        "datetime",
        "logging",
        "random",
        "threading",
        "time",
        "uuid",
    }
    forbidden_text = {
        "ContextVar",
        "GlobalTracer",
        "TracerSingleton",
        "TraceSinkPort",
        ".emit(",
        "datetime.now",
        "uuid4",
    }

    assert imports.isdisjoint(forbidden_imports)
    assert all(fragment not in text for fragment in forbidden_text)
    assert _fields(TRACE_POLICY, "TraceContextPolicy") == set()


def test_trace_helpers_and_factory_have_no_infrastructure_or_authority_import() -> None:
    imports = {
        module
        for path in (TRACE_POLICY, SPAN_CATALOG, SPAN_FACTORY)
        for module in _imports(path)
    }
    forbidden = {
        "backend.adapters",
        "backend.infrastructure",
        "agent_runtime.application_routing",
        "agent_runtime.gates",
        "agent_runtime.policy",
        "agent_runtime.recovery",
        "agent_runtime.security",
        "agent_runtime.tools",
        "observability.ports",
        "opentelemetry",
        "prometheus",
        "structlog",
    }
    assert all(
        fragment not in module for fragment in forbidden for module in imports
    )


def test_contract_meta_and_delegation_legacy_mappings_are_not_migrated() -> None:
    metadata = (
        BACKEND / "agent_runtime" / "contracts" / "common" / "metadata.py"
    )
    delegation = (
        BACKEND / "agent_runtime" / "contracts" / "planning" / "delegation.py"
    )
    assert "trace_flags: Mapping[str, object]" in metadata.read_text(encoding="utf-8")
    assert "trace_context: Mapping[str, object]" in delegation.read_text(
        encoding="utf-8"
    )
    assert all("observability" not in module for module in _imports(metadata))
    assert all("observability" not in module for module in _imports(delegation))
    assert "trace_flags" not in TRACE_POLICY.read_text(encoding="utf-8")
    assert "DelegationEnvelope" not in TRACE_POLICY.read_text(encoding="utf-8")


def test_runtime_routing_and_recovery_remain_uninstrumented() -> None:
    protected_roots = (
        BACKEND / "agent_runtime" / "runtime",
        BACKEND / "agent_runtime" / "recovery",
        BACKEND / "agent_runtime" / "application_routing",
        BACKEND / "agent_runtime" / "tools",
        BACKEND / "agent_runtime" / "gates",
    )
    for root in protected_roots:
        for path in _python_files(root):
            assert all(
                "agent_runtime.observability" not in module
                and "contracts.observability" not in module
                for module in _imports(path)
            )


def test_trace_is_not_injected_into_tool_or_application_payload_contracts() -> None:
    paths = (
        BACKEND
        / "agent_runtime"
        / "contracts"
        / "tools"
        / "tool_call_request.py",
        BACKEND
        / "agent_runtime"
        / "contracts"
        / "application"
        / "use_case_request.py",
        BACKEND / "agent_runtime" / "runtime" / "routing" / "model.py",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert 'arguments["trace_id"]' not in text
        assert 'payload["trace_id"]' not in text
        assert 'requested_effect["trace' not in text
        assert all("observability" not in module for module in _imports(path))


def test_correlation_trace_and_span_identities_remain_distinct() -> None:
    assert _fields(TRACE_CONTRACT, "TraceId") == {"value"}
    assert _fields(TRACE_CONTRACT, "SpanId") == {"value"}
    assert _fields(TRACE_CONTRACT, "TraceContext") == {
        "trace_id",
        "span_id",
        "parent_span_id",
        "sampling_decision",
    }
    correlation = (
        BACKEND / "shared_kernel" / "correlation" / "correlation_id.py"
    )
    assert "TraceId" not in correlation.read_text(encoding="utf-8")
    assert "CorrelationId" not in TRACE_CONTRACT.read_text(encoding="utf-8")


def test_span_record_remains_completed_data_only_and_metrics_forbid_trace_labels() -> None:
    span = (
        BACKEND / "agent_runtime" / "contracts" / "observability" / "span.py"
    )
    metric = (
        BACKEND / "agent_runtime" / "contracts" / "observability" / "metric.py"
    )
    assert {"started_at", "ended_at"} <= _fields(span, "SpanRecord")
    assert "SpanStart" not in "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(OBSERVABILITY)
    )
    metric_text = metric.read_text(encoding="utf-8")
    assert '"trace_id"' in metric_text
    assert '"span_id"' in metric_text


def test_d_adds_no_external_dependency() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["dependencies"] == ["openai>=3.5,<4"]
