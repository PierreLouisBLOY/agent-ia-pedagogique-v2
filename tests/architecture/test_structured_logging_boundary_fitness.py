from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OBSERVABILITY = BACKEND / "agent_runtime" / "observability"
MAPPER = OBSERVABILITY / "log_mapper.py"
CATALOG = OBSERVABILITY / "log_catalog.py"


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _imports(path: Path) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_structured_log_mappers_live_only_in_observability() -> None:
    definitions = {
        node.name
        for path in _python_files(BACKEND)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef)
        and node.name.startswith("structured_log_from_")
    }
    assert definitions == {
        "structured_log_from_workflow_event",
        "structured_log_from_security_event",
        "structured_log_from_error_envelope",
        "structured_log_from_execution_directive",
    }
    mapper_definitions = {
        node.name
        for node in ast.walk(ast.parse(MAPPER.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef)
    }
    assert definitions <= mapper_definitions


def test_mappers_are_data_only_and_use_no_dynamic_source_serialization() -> None:
    text = MAPPER.read_text(encoding="utf-8")
    forbidden = {
        ".__dict__",
        "asdict(",
        "datetime.now",
        "GlobalLogger",
        "json.dumps",
        "repr(",
        "uuid",
        "vars(",
        ".emit(",
    }
    assert all(fragment not in text for fragment in forbidden)
    assert "trace_flags" not in text


def test_mappers_import_no_authority_sink_infrastructure_or_exporter() -> None:
    imports = _imports(MAPPER) | _imports(CATALOG)
    forbidden_fragments = {
        "backend.adapters",
        "backend.infrastructure",
        "agent_runtime.application_routing",
        "agent_runtime.gates",
        "agent_runtime.recovery",
        "agent_runtime.tools",
        "observability.ports",
        "opentelemetry",
        "prometheus",
        "structlog",
    }
    assert all(
        fragment not in module
        for fragment in forbidden_fragments
        for module in imports
    )


def test_runtime_and_recovery_remain_uninstrumented() -> None:
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


def test_source_contracts_remain_free_of_observability_semantics() -> None:
    source_paths = (
        BACKEND
        / "agent_runtime"
        / "contracts"
        / "events"
        / "workflow_event.py",
        BACKEND
        / "agent_runtime"
        / "contracts"
        / "security"
        / "security_event.py",
        BACKEND
        / "agent_runtime"
        / "contracts"
        / "errors"
        / "error_envelope.py",
    )
    for path in source_paths:
        imports = _imports(path)
        assert all("observability" not in module for module in imports)


def test_c_adds_no_dependency() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["dependencies"] == ["openai>=3.5,<4"]
