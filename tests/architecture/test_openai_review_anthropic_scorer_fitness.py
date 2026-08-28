from __future__ import annotations

import ast
import inspect
import tomllib
from dataclasses import fields
from pathlib import Path

from backend.adapters.outbound.review.openai import OpenAIReviewAdapter
from backend.agent_runtime.agents.review import (
    ReviewPort,
    ReviewPortRequest,
    ReviewPortResult,
)
from evaluation_harness import NormalizedScore, ScorerOutcome, ScoreStatus
from evaluation_harness.scoring.ports import EvaluationScorerPort
from tests.providers.anthropic import AnthropicEvaluationScorer

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
HARNESS = ROOT / "evaluation_harness"
ANTHROPIC_OWNER = ROOT / "tests" / "providers" / "anthropic"
REVIEW_OWNER = BACKEND / "adapters" / "outbound" / "review" / "openai"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            result.add(node.module)
    return result


def _python_files(owner: Path) -> list[Path]:
    return [path for path in owner.rglob("*.py") if "__pycache__" not in path.parts]


def test_runtime_dependency_stays_openai_only_and_anthropic_is_optional() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    assert project["dependencies"] == ["openai>=3.5,<4"]
    assert project["optional-dependencies"] == {
        "calibration": ["anthropic>=1.2,<2"]
    }


def test_anthropic_sdk_imports_are_confined_to_calibration_owner() -> None:
    importers = [
        path
        for owner in (BACKEND, HARNESS, ROOT / "tests")
        for path in _python_files(owner)
        if any(name == "anthropic" or name.startswith("anthropic.") for name in _imports(path))
    ]
    assert importers
    assert all(path.is_relative_to(ANTHROPIC_OWNER) for path in importers)


def test_backend_and_harness_dependency_directions_remain_closed() -> None:
    backend_violations = [
        path.relative_to(ROOT).as_posix()
        for path in _python_files(BACKEND)
        if any(
            name == "evaluation_harness"
            or name.startswith("evaluation_harness.")
            or name == "tests.providers"
            or name.startswith("tests.providers.")
            for name in _imports(path)
        )
    ]
    harness_violations = [
        path.relative_to(ROOT).as_posix()
        for path in _python_files(HARNESS)
        if any(
            name == forbidden or name.startswith(f"{forbidden}.")
            for forbidden in ("backend.infrastructure", "openai", "anthropic")
            for name in _imports(path)
        )
    ]
    assert backend_violations == []
    assert harness_violations == []


def test_existing_review_and_scoring_contracts_are_reused_exactly() -> None:
    assert inspect.signature(ReviewPort.review).parameters.keys() == {
        "self",
        "request",
    }
    assert tuple(item.name for item in fields(ReviewPortRequest)) == (
        "source_step_id",
        "operation",
        "capability_id",
        "target_production_ref",
        "review_dimensions",
        "target_content",
        "target_payload",
        "criteria",
        "evidence_refs",
        "coverage_context",
        "resolved_inputs",
        "output_contract",
        "review_budget",
    )
    assert tuple(item.name for item in fields(ReviewPortResult)) == (
        "source_step_id",
        "operation",
        "status",
        "structured_payload",
        "technical_findings",
        "evidence_refs_used",
        "limitations",
        "warnings",
        "uncertainties",
        "execution_metadata",
    )
    assert inspect.signature(EvaluationScorerPort.score).parameters.keys() == {
        "self",
        "scorer_ref",
        "observations",
    }
    assert tuple(item.name for item in fields(ScorerOutcome)) == ("status", "score")
    assert tuple(item.name for item in fields(NormalizedScore)) == (
        "numerator",
        "denominator",
    )
    assert tuple(item.value for item in ScoreStatus) == (
        "SCORED",
        "INCONCLUSIVE",
        "ERROR",
    )


def test_openai_transport_and_secret_resolver_are_not_duplicated() -> None:
    class_owners: dict[str, list[str]] = {
        "OpenAISDKResponsesTransport": [],
        "EnvironmentProviderSecretResolver": [],
    }
    for path in _python_files(BACKEND):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in class_owners:
                class_owners[node.name].append(path.relative_to(ROOT).as_posix())
    assert class_owners == {
        "OpenAISDKResponsesTransport": [
            "backend/adapters/outbound/openai/transport.py"
        ],
        "EnvironmentProviderSecretResolver": [
            "backend/infrastructure/config/secrets/provider.py"
        ],
    }


def test_adapters_have_no_authority_retry_fallback_or_forbidden_owner_imports() -> None:
    forbidden_imports = (
        "backend.agent_runtime.gates",
        "backend.agent_runtime.observability",
        "backend.agent_runtime.recovery",
        "backend.agent_runtime.registry",
        "evaluation_harness.runner",
    )
    violations: list[str] = []
    loops: list[str] = []
    for path in _python_files(REVIEW_OWNER) + _python_files(ANTHROPIC_OWNER):
        imported = _imports(path)
        if any(
            name == forbidden or name.startswith(f"{forbidden}.")
            for name in imported
            for forbidden in forbidden_imports
        ):
            violations.append(path.relative_to(ROOT).as_posix())
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(isinstance(node, (ast.While, ast.AsyncFor)) for node in ast.walk(tree)):
            loops.append(path.relative_to(ROOT).as_posix())
    assert violations == []
    assert loops == []
    assert not hasattr(OpenAIReviewAdapter, "approve")
    assert not hasattr(OpenAIReviewAdapter, "promote")
    assert not hasattr(AnthropicEvaluationScorer, "approve")
    assert not hasattr(AnthropicEvaluationScorer, "gate")


def test_no_openai_scorer_fallback_or_embedding_implementation_exists() -> None:
    scorer_source = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(ANTHROPIC_OWNER)
    )
    review_factory = (
        BACKEND / "infrastructure" / "composition" / "factories" / "openai.py"
    ).read_text(encoding="utf-8")
    assert "fallback_model_profile_ids" not in scorer_source
    assert "fallback_model_profile_ids" not in review_factory
    assert "embedding" not in scorer_source.casefold()
