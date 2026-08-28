from __future__ import annotations

import ast
import inspect
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.agent_runtime.agents.generation.generation_ports import GenerationPort
from backend.agent_runtime.agents.review.review_ports import ReviewPort
from backend.agent_runtime.registry import BASELINE_TOOL_REGISTRY
from backend.core_contracts.capability import CapabilityId
from backend.infrastructure.config.effective_config.provider import (
    EffectiveProviderConfiguration,
)
from backend.infrastructure.config.schemas.provider import (
    ModelContextLimits,
    ProviderInvocationLimits,
    ProviderWorkloadKind,
)
from evaluation_harness.scoring.ports import EvaluationScorerPort

ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = ROOT / "backend" / "infrastructure" / "config"
PROVIDER_FILES = (
    CONFIG_ROOT / "schemas" / "provider.py",
    CONFIG_ROOT / "loaders" / "provider.py",
    CONFIG_ROOT / "effective_config" / "provider.py",
    CONFIG_ROOT / "secrets" / "provider.py",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def _class_definitions(root: Path, class_name: str) -> list[str]:
    definitions: list[str] = []
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.ClassDef) and node.name == class_name
            for node in ast.walk(tree)
        ):
            definitions.append(path.relative_to(ROOT).as_posix())
    return definitions


def test_provider_foundation_has_the_canonical_infrastructure_owner() -> None:
    assert all(path.is_file() for path in PROVIDER_FILES)
    assert not (ROOT / "backend" / "providers").exists()
    assert not any(
        path.name == "provider.py"
        for owner in (
            ROOT / "backend" / "modules",
            ROOT / "backend" / "agent_runtime",
        )
        for path in owner.rglob("*.py")
    )


def test_provider_foundation_imports_no_sdk_network_or_authority_owner() -> None:
    forbidden_prefixes = (
        "aiohttp",
        "anthropic",
        "backend.agent_runtime.gates",
        "backend.agent_runtime.recovery",
        "backend.agent_runtime.registry",
        "backend.core_contracts.capability",
        "evaluation_harness",
        "http.client",
        "httpx",
        "openai",
        "requests",
        "socket",
        "urllib",
    )
    imported = {name for path in PROVIDER_FILES for name in _imports(path)}
    assert not {
        name
        for name in imported
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in forbidden_prefixes)
    }


def test_production_provider_configuration_selects_no_real_provider_or_model() -> None:
    source = "\n".join(path.read_text(encoding="utf-8").casefold() for path in PROVIDER_FILES)
    forbidden = (
        "anthropic",
        "azure openai",
        "gemini",
        "huggingface",
        "langchain",
        "litellm",
        "llamaindex",
        "mistral",
        "ollama",
        "openai",
    )
    assert all(token not in source for token in forbidden)


def test_workload_routing_is_distinct_from_capability_authority() -> None:
    assert ProviderWorkloadKind is not CapabilityId
    assert not issubclass(ProviderWorkloadKind, CapabilityId)
    assert tuple(item.value for item in ProviderWorkloadKind) == (
        "GENERATION",
        "CORRECTION",
        "REVIEW",
        "EVALUATION_SCORING",
    )
    assert BASELINE_TOOL_REGISTRY.by_capability(CapabilityId("CAP-T04")) == ()


def test_existing_ports_are_reused_without_duplicates() -> None:
    assert inspect.signature(GenerationPort.generate).parameters.keys() == {
        "self",
        "request",
    }
    assert inspect.signature(ReviewPort.review).parameters.keys() == {
        "self",
        "request",
    }
    assert inspect.signature(EvaluationScorerPort.score).parameters.keys() == {
        "self",
        "scorer_ref",
        "observations",
    }
    assert _class_definitions(ROOT / "backend", "GenerationPort") == [
        "backend/agent_runtime/agents/generation/generation_ports.py"
    ]
    assert _class_definitions(ROOT / "backend", "ReviewPort") == [
        "backend/agent_runtime/agents/review/review_ports.py"
    ]
    assert _class_definitions(ROOT / "evaluation_harness", "EvaluationScorerPort") == [
        "evaluation_harness/scoring/ports.py"
    ]
    assert _class_definitions(ROOT / "backend", "ProviderGenerationPort") == []
    assert _class_definitions(ROOT / "backend", "ProviderReviewPort") == []


def test_limits_context_and_effective_secret_fields_remain_separate() -> None:
    invocation_fields = {item.name for item in fields(ProviderInvocationLimits)}
    assert invocation_fields == {
        "max_attempts",
        "call_timeout_milliseconds",
        "max_input_tokens",
        "max_output_tokens",
        "max_total_tokens",
        "max_cost",
    }
    assert "deadline" not in invocation_fields
    assert "max_retries" not in invocation_fields

    context_fields = {item.name for item in fields(ModelContextLimits)}
    assert context_fields == {
        "context_window_tokens",
        "max_provider_input_tokens",
        "reserved_output_tokens",
    }
    assert "pedagogical_context" not in context_fields

    effective_fields = {item.name for item in fields(EffectiveProviderConfiguration)}
    assert effective_fields == {
        "schema_version",
        "provider_profiles",
        "model_profiles",
        "routes",
    }
    assert not effective_fields.intersection(
        {"secret", "secret_value", "credential_value", "provider_client"}
    )


def test_agent_domain_and_application_do_not_import_provider_secrets() -> None:
    forbidden_import = "backend.infrastructure.config.secrets"
    roots = (
        ROOT / "backend" / "agent_runtime",
        ROOT / "backend" / "core_contracts",
        ROOT / "backend" / "modules",
    )
    violations = [
        path.relative_to(ROOT).as_posix()
        for owner in roots
        for path in owner.rglob("*.py")
        if any(
            name == forbidden_import or name.startswith(f"{forbidden_import}.")
            for name in _imports(path)
        )
    ]
    assert violations == []


def test_runtime_dependencies_remain_empty() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["dependencies"] == []
