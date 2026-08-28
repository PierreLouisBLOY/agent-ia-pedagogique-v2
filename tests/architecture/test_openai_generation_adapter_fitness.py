from __future__ import annotations

import ast
import inspect
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.adapters.outbound.generation.openai import OpenAIGenerationAdapter
from backend.agent_runtime.agents.generation import (
    GenerationPort,
    GenerationPortRequest,
    GenerationPortResult,
)

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OPENAI_ADAPTER = BACKEND / "adapters" / "outbound" / "generation" / "openai"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_openai_sdk_import_is_confined_to_the_concrete_transport() -> None:
    sdk_importers = [
        path.relative_to(ROOT).as_posix()
        for owner in (BACKEND, ROOT / "tests")
        for path in owner.rglob("*.py")
        if "__pycache__" not in path.parts
        and any(
            name == "openai" or name.startswith("openai.")
            for name in _imports(path)
        )
    ]
    assert sdk_importers == [
        "backend/adapters/outbound/openai/transport.py",
        "tests/unit/test_openai_responses_transport.py",
    ]


def test_provider_sdk_and_dtos_do_not_leak_into_agent_or_domain_owners() -> None:
    forbidden = (
        "openai",
        "backend.adapters.outbound.generation.openai",
        "backend.adapters.outbound.openai",
    )
    owners = (
        BACKEND / "agent_runtime",
        BACKEND / "modules",
        BACKEND / "shared_kernel",
    )
    violations = [
        path.relative_to(ROOT).as_posix()
        for owner in owners
        for path in owner.rglob("*.py")
        if any(
            name == prefix or name.startswith(f"{prefix}.")
            for name in _imports(path)
            for prefix in forbidden
        )
    ]
    assert violations == []


def test_existing_generation_port_contract_is_reused_unchanged() -> None:
    assert isinstance(
        OpenAIGenerationAdapter.__new__(OpenAIGenerationAdapter),
        OpenAIGenerationAdapter,
    )
    assert inspect.signature(GenerationPort.generate).parameters.keys() == {
        "self",
        "request",
    }
    assert tuple(item.name for item in fields(GenerationPortRequest)) == (
        "operation",
        "source_step_id",
        "production_kind",
        "objective",
        "output_format",
        "pedagogical_context",
        "resolved_inputs",
        "constraints",
        "evidence_refs",
        "target_ref",
        "target_version_ref",
        "expected_sections",
        "output_contract",
    )
    assert tuple(item.name for item in fields(GenerationPortResult)) == (
        "source_step_id",
        "operation",
        "status",
        "content",
        "structured_payload",
        "evidence_refs_used",
        "warnings",
        "uncertainties",
        "execution_metadata",
        "operation_details",
        "content_label",
    )


def test_adapter_contains_no_retry_loop_or_forbidden_authority_import() -> None:
    forbidden = (
        "backend.agent_runtime.gates",
        "backend.agent_runtime.observability",
        "backend.agent_runtime.recovery",
        "backend.agent_runtime.registry",
        "evaluation_harness",
    )
    violations: set[str] = set()
    while_nodes: list[str] = []
    for path in OPENAI_ADAPTER.rglob("*.py"):
        imported = _imports(path)
        violations.update(
            name
            for name in imported
            if any(name == item or name.startswith(f"{item}.") for item in forbidden)
        )
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(isinstance(node, ast.While) for node in ast.walk(tree)):
            while_nodes.append(path.name)
    assert violations == set()
    assert while_nodes == []


def test_dependency_surface_contains_no_framework_or_other_provider_sdk() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["dependencies"] == ["openai>=3.5,<4"]
    source = "\n".join(path.read_text(encoding="utf-8").casefold() for path in OPENAI_ADAPTER.rglob("*.py"))
    assert all(
        name not in source
        for name in ("anthropic", "langchain", "litellm", "llamaindex", "mistral")
    )
