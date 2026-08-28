from pathlib import Path

from backend.agent_runtime.orchestration.workflows import (
    BASELINE_WORKFLOW_CATALOG,
    WorkflowKind,
)
from backend.agent_runtime.registry import BASELINE_CAPABILITY_REGISTRY
from backend.core_contracts.capability import CapabilityId

ROOT = Path(__file__).resolve().parents[2]
E_BINDINGS = ROOT / "tests/e2e/core/assessment_bindings.py"
E_ADAPTER = ROOT / "tests/e2e/core/assessment_adapters.py"


def _package_source(relative: str) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / relative).rglob("*.py"))
    ).casefold()


def test_e_bindings_are_test_only_provider_neutral_and_offline() -> None:
    source = (E_BINDINGS.read_text(encoding="utf-8") + E_ADAPTER.read_text(encoding="utf-8")).casefold()

    assert E_BINDINGS.is_relative_to(ROOT / "tests")
    assert E_ADAPTER.is_relative_to(ROOT / "tests")
    for forbidden in (
        "import sqlite3",
        "requests.",
        "httpx.",
        "openai",
        "anthropic",
        "socket",
        "cap-t02",
        "truth_score",
        "quality_score",
    ):
        assert forbidden not in source


def test_backend_does_not_depend_on_e_bindings_or_evaluation_harness() -> None:
    backend = _package_source("backend")

    assert "tests.e2e.core.assessment" not in backend
    assert "assessment_bindings" not in backend
    assert "assessment_adapters" not in backend
    assert "evaluation_harness" not in backend


def test_agent_packages_keep_storage_and_cross_agent_boundaries() -> None:
    generation = _package_source("backend/agent_runtime/agents/generation")
    review = _package_source("backend/agent_runtime/agents/review")
    evidence = _package_source("backend/agent_runtime/agents/evidence")

    for source in (generation, review, evidence):
        assert "sqlite" not in source
        assert "backend.adapters.outbound" not in source
        assert "backend.modules." not in source
    assert "agents.evidence" not in generation
    assert "agents.review" not in generation
    assert "agents.generation" not in review


def test_e_reuses_exact_capabilities_and_workflows() -> None:
    capability_codes = (
        "CAP-E01",
        "CAP-E02",
        "CAP-E03",
        "CAP-G01",
        "CAP-G03",
        "CAP-V01",
        "CAP-V02",
        "CAP-R02",
        "CAP-A01",
        "CAP-A02",
        "CAP-O04",
        "CAP-O05",
        "CAP-O06",
    )
    assert tuple(
        BASELINE_CAPABILITY_REGISTRY.get(CapabilityId(code)).capability_id.value
        for code in capability_codes
    ) == capability_codes
    workflow_kinds = (
        WorkflowKind.WF_0,
        WorkflowKind.WF_1,
        WorkflowKind.WF_3,
        WorkflowKind.WF_6,
        WorkflowKind.WF_7,
        WorkflowKind.WF_8,
        WorkflowKind.WF_9,
        WorkflowKind.WF_11,
    )
    assert tuple(
        BASELINE_WORKFLOW_CATALOG.get(kind).workflow_kind for kind in workflow_kinds
    ) == workflow_kinds


def test_gate_decision_is_external_and_promotion_uses_application_route() -> None:
    agents = _package_source("backend/agent_runtime/agents")
    bindings = E_BINDINGS.read_text(encoding="utf-8")

    assert "GateDecision(" not in agents
    assert '"application.request_promotion"' in bindings
    assert '"CAP-A02"' in bindings
    assert "router.route(" in bindings
    assert "RecordingGateDecisionSource" in bindings


def test_fake_ports_and_raw_report_checks_remain_under_tests() -> None:
    integration = (
        ROOT / "tests/integration/test_assessment_correction_qcm_e2e.py"
    ).read_text(encoding="utf-8")
    bindings = E_BINDINGS.read_text(encoding="utf-8")

    assert "RecordingGenerationPort" in bindings
    assert "RecordingReviewPort" in bindings
    assert "RecordingEvidenceSearchPort" in bindings
    assert 'not in json_artifact.content' in integration
    assert 'not in markdown_artifact.content' in integration
