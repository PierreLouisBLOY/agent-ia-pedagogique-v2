from pathlib import Path

from backend.agent_runtime.orchestration.workflows import (
    BASELINE_WORKFLOW_CATALOG,
    WorkflowKind,
)
from backend.agent_runtime.registry import BASELINE_CAPABILITY_REGISTRY
from backend.core_contracts.capability import CapabilityId

ROOT = Path(__file__).resolve().parents[2]
D_ADAPTER = ROOT / "tests/e2e/core/generation_adapters.py"


def _package_source(relative: str) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / relative).rglob("*.py"))
    ).casefold()


def test_d_binding_is_test_only_and_provider_neutral() -> None:
    source = D_ADAPTER.read_text(encoding="utf-8").casefold()

    assert D_ADAPTER.is_relative_to(ROOT / "tests")
    for forbidden in (
        "import sqlite3",
        "requests.",
        "httpx.",
        "openai",
        "anthropic",
        "socket",
    ):
        assert forbidden not in source


def test_agents_keep_sql_repository_and_cross_agent_boundaries() -> None:
    generation = _package_source("backend/agent_runtime/agents/generation")
    review = _package_source("backend/agent_runtime/agents/review")

    for source in (generation, review):
        assert "sqlite" not in source
        assert "backend.modules." not in source
        assert "backend.adapters.outbound" not in source
    assert "agents.evidence" not in generation
    assert "agents.review" not in generation
    assert "agents.generation" not in review


def test_production_never_depends_on_e2e_bindings() -> None:
    production = _package_source("backend")

    assert "tests.e2e" not in production
    assert "generation_adapters" not in production


def test_d_reuses_exact_canonical_capabilities_and_workflows() -> None:
    assert tuple(
        BASELINE_CAPABILITY_REGISTRY.get(CapabilityId(code)).capability_id.value
        for code in ("CAP-E01", "CAP-G01", "CAP-G02", "CAP-V01", "CAP-O05")
    ) == ("CAP-E01", "CAP-G01", "CAP-G02", "CAP-V01", "CAP-O05")
    assert tuple(
        BASELINE_WORKFLOW_CATALOG.get(kind).workflow_kind
        for kind in (
            WorkflowKind.WF_2,
            WorkflowKind.WF_4,
            WorkflowKind.WF_5,
            WorkflowKind.WF_10,
        )
    ) == (
        WorkflowKind.WF_2,
        WorkflowKind.WF_4,
        WorkflowKind.WF_5,
        WorkflowKind.WF_10,
    )


def test_agents_do_not_construct_external_gate_decisions() -> None:
    agents = _package_source("backend/agent_runtime/agents")

    assert "gatedecision(" not in agents
