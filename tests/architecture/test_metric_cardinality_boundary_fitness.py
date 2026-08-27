from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OBSERVABILITY = BACKEND / "agent_runtime" / "observability"
MAPPER = OBSERVABILITY / "metric_mapper.py"
CATALOG = OBSERVABILITY / "metric_catalog.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_metric_catalog_contains_no_dynamic_descriptor_construction() -> None:
    tree = _tree(CATALOG)
    descriptor_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_descriptor"
    ]

    assert descriptor_calls
    assert all(
        call.args
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].value.id == "MetricCode"
        for call in descriptor_calls
    )
    assert "dict[str, MetricDescriptor]" not in CATALOG.read_text(encoding="utf-8")


def test_metric_mapper_never_reads_opaque_mappings_or_sensitive_fields() -> None:
    read_attributes = {
        node.attr
        for node in ast.walk(_tree(MAPPER))
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
    }
    forbidden = {
        "metrics",
        "retrieval_metrics",
        "run_id",
        "step_id",
        "correlation_id",
        "trace_id",
        "span_id",
        "invocation_id",
        "record_id",
        "error_code",
        "reason_code",
        "message",
        "details",
        "metadata",
        "refs",
    }

    assert read_attributes.isdisjoint(forbidden)
    assert "__dict__" not in MAPPER.read_text(encoding="utf-8")
    assert "asdict" not in MAPPER.read_text(encoding="utf-8")


def test_e_adds_no_sink_call_backend_or_runtime_instrumentation() -> None:
    metric_files = tuple(sorted(OBSERVABILITY.glob("metric_*.py")))
    imports = {module for path in metric_files for module in _imports(path)}
    forbidden_imports = {
        "backend.adapters",
        "backend.infrastructure",
        "opentelemetry",
        "prometheus_client",
    }

    assert all(
        not module.startswith(fragment)
        for module in imports
        for fragment in forbidden_imports
    )
    production_text = "\n".join(path.read_text(encoding="utf-8") for path in metric_files)
    assert ".emit(" not in production_text
    assert "MetricSinkPort" not in production_text
    assert "Thread" not in production_text

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


def test_metric_points_cannot_become_recovery_or_budget_inputs() -> None:
    protected = (
        BACKEND / "agent_runtime" / "recovery",
        BACKEND / "agent_runtime" / "gates",
        BACKEND / "agent_runtime" / "policy",
    )
    for root in protected:
        for path in _python_files(root):
            text = path.read_text(encoding="utf-8")
            assert "MetricPoint" not in text
            assert "metric_points_from_" not in text


def test_project_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["dependencies"] == []
