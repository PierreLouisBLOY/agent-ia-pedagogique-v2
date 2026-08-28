from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
AGENT_OBSERVABILITY = BACKEND / "agent_runtime" / "observability"
INFRA_OBSERVABILITY = BACKEND / "infrastructure" / "observability"


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


def test_agent_runtime_delivery_model_never_imports_infrastructure_or_io() -> None:
    delivery_files = (
        AGENT_OBSERVABILITY / "delivery_model.py",
        AGENT_OBSERVABILITY / "delivery_policy.py",
    )
    forbidden = {
        "backend.infrastructure",
        "io",
        "json",
        "logging",
        "pathlib",
        "queue",
        "threading",
    }

    for path in delivery_files:
        imports = _imports(path)
        assert all(
            not module.startswith(fragment)
            for module in imports
            for fragment in forbidden
        )


def test_infrastructure_delivery_does_not_reuse_authoritative_mechanisms() -> None:
    imports = {
        module
        for path in _python_files(INFRA_OBSERVABILITY)
        for module in _imports(path)
    }
    forbidden_modules = {
        "backend.agent_runtime.gates",
        "backend.agent_runtime.recovery",
        "backend.agent_runtime.sandbox",
        "backend.agent_runtime.security",
        "backend.adapters",
        "opentelemetry",
        "prometheus_client",
        "requests",
    }
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in _python_files(INFRA_OBSERVABILITY)
    )

    assert all(
        not module.startswith(fragment)
        for module in imports
        for fragment in forbidden_modules
    )
    for forbidden_name in (
        "EffectState",
        "ReplayGuard",
        "RetryPolicy",
        "CircuitBreaker",
        "SecurityEvent",
        "ErrorEnvelope",
        "Idempotency",
    ):
        assert forbidden_name not in text


def test_serializers_are_explicit_allowlists_not_generic_dataclass_exports() -> None:
    serializer = INFRA_OBSERVABILITY / "serialization.py"
    tree = _tree(serializer)
    function_names = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    text = serializer.read_text(encoding="utf-8")

    assert {
        "serialize_log_record",
        "serialize_span_record",
        "serialize_metric_point",
    }.issubset(function_names)
    for forbidden in (
        "asdict",
        "__dict__",
        "is_dataclass",
        "dataclasses.fields",
        "repr(",
        "default=str",
    ):
        assert forbidden not in text
    assert "MAX_SERIALIZED_RECORD_BYTES: Final = 65_536" in text
    assert '"type": channel.value' in text
    assert '"schema_version"' in text


def test_delivery_is_bounded_without_retry_worker_file_or_global_logger() -> None:
    policy = (AGENT_OBSERVABILITY / "delivery_policy.py").read_text(
        encoding="utf-8"
    )
    infra = "\n".join(
        path.read_text(encoding="utf-8")
        for path in _python_files(INFRA_OBSERVABILITY)
    )

    assert "MAX_BUFFER_ITEMS: Final = 4_096" in policy
    assert "MAX_BUFFER_BYTES: Final = 64 * 1_024 * 1_024" in policy
    assert "MAX_FLUSH_ITEMS: Final = 1_024" in policy
    for forbidden in (
        "Thread(",
        "Timer(",
        "sleep(",
        "Queue(",
        "open(",
        "sqlite",
        "WAL",
        "retry",
        "stdout",
        "getLogger",
        "basicConfig",
    ):
        assert forbidden not in infra


def test_f_adds_no_runtime_or_recovery_instrumentation() -> None:
    protected_roots = (
        BACKEND / "agent_runtime" / "runtime",
        BACKEND / "agent_runtime" / "recovery",
        BACKEND / "agent_runtime" / "application_routing",
        BACKEND / "agent_runtime" / "tools",
        BACKEND / "agent_runtime" / "gates",
        BACKEND / "agent_runtime" / "orchestration",
    )
    for root in protected_roots:
        for path in _python_files(root):
            imports = _imports(path)
            assert all(
                "infrastructure.observability" not in module
                and "agent_runtime.observability" not in module
                and "contracts.observability" not in module
                for module in imports
            )


def test_failure_path_has_no_recursive_observation_or_raw_exception_storage() -> None:
    sinks = (INFRA_OBSERVABILITY / "sinks.py").read_text(encoding="utf-8")

    assert "StructuredLogRecord(" not in sinks
    assert "SecurityEvent(" not in sinks
    assert "except Exception as" not in sinks
    assert "str(error)" not in sinks
    assert "repr(error)" not in sinks
    assert ".args" not in sinks


def test_project_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["dependencies"] == ["openai>=3.5,<4"]
