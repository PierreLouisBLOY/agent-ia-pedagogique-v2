from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CONTRACTS = BACKEND / "agent_runtime" / "contracts" / "observability"
OBSERVABILITY = BACKEND / "agent_runtime" / "observability"


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


def test_observability_contracts_are_unique_and_live_in_the_contract_boundary() -> None:
    expected = {
        "TraceContext": CONTRACTS / "trace.py",
        "StructuredLogRecord": CONTRACTS / "log.py",
        "SpanRecord": CONTRACTS / "span.py",
        "MetricDescriptor": CONTRACTS / "metric.py",
        "MetricPoint": CONTRACTS / "metric.py",
    }
    for class_name, path in expected.items():
        assert _defined_classes(BACKEND, class_name) == (path,)


def test_existing_event_error_and_correlation_contracts_remain_distinct() -> None:
    assert _defined_classes(BACKEND, "WorkflowEvent") == (
        BACKEND / "agent_runtime" / "contracts" / "events" / "workflow_event.py",
    )
    assert _defined_classes(BACKEND, "SecurityEvent") == (
        BACKEND / "agent_runtime" / "contracts" / "security" / "security_event.py",
    )
    assert _defined_classes(BACKEND, "ErrorEnvelope") == (
        BACKEND / "agent_runtime" / "contracts" / "errors" / "error_envelope.py",
    )
    assert _defined_classes(BACKEND, "CorrelationId") == (
        BACKEND / "shared_kernel" / "correlation" / "correlation_id.py",
    )
    assert _defined_classes(BACKEND, "TraceId") == (CONTRACTS / "trace.py",)


def test_observability_contracts_have_no_authority_or_free_content_fields() -> None:
    forbidden = {
        "allow",
        "authority",
        "capability",
        "decision",
        "delegate",
        "document",
        "effect_state",
        "gate",
        "message",
        "payload",
        "permission",
        "promote",
        "prompt",
        "recovery",
        "retry",
    }
    fields_by_contract = {
        "TraceContext": _fields(CONTRACTS / "trace.py", "TraceContext"),
        "StructuredLogRecord": _fields(
            CONTRACTS / "log.py", "StructuredLogRecord"
        ),
        "SpanRecord": _fields(CONTRACTS / "span.py", "SpanRecord"),
        "MetricDescriptor": _fields(
            CONTRACTS / "metric.py", "MetricDescriptor"
        ),
        "MetricPoint": _fields(CONTRACTS / "metric.py", "MetricPoint"),
    }
    for contract_fields in fields_by_contract.values():
        assert contract_fields.isdisjoint(forbidden)


def test_observability_contracts_have_no_backend_or_telemetry_dependency() -> None:
    forbidden_fragments = {
        "backend.adapters",
        "backend.infrastructure",
        "logging",
        "opentelemetry",
        "prometheus",
        "requests",
        "structlog",
    }
    imports = {
        module
        for path in (*_python_files(CONTRACTS), *_python_files(OBSERVABILITY))
        for module in _imports(path)
    }
    assert all(
        fragment not in module
        for fragment in forbidden_fragments
        for module in imports
    )


def test_sink_boundary_contains_only_three_distinct_protocols() -> None:
    ports = _tree(OBSERVABILITY / "ports.py")
    protocols = {
        node.name
        for node in ports.body
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(base, ast.Name) and base.id == "Protocol" for base in node.bases
        )
    }
    assert protocols == {"LogSinkPort", "TraceSinkPort", "MetricSinkPort"}
    production_text = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(OBSERVABILITY)
    )
    assert "TelemetrySinkPort" not in production_text
    assert "InMemory" not in production_text


def test_trace_flags_remain_legacy_mapping_without_trace_context_dependency() -> None:
    metadata = BACKEND / "agent_runtime" / "contracts" / "common" / "metadata.py"
    text = metadata.read_text(encoding="utf-8")

    assert "trace_flags: Mapping[str, object]" in text
    assert "TraceContext" not in text
    assert "contracts.observability" not in _imports(metadata)


def test_b_adds_no_runtime_or_recovery_instrumentation() -> None:
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


def test_project_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["dependencies"] == ["openai>=3.5,<4"]
