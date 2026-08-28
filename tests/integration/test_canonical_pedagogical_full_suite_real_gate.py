from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.agent_runtime.agents.evidence import RetrievalCoordinationMode
from backend.agent_runtime.contracts import ProductionValidationState
from backend.agent_runtime.gates import GateResolutionDisposition
from backend.infrastructure.config.loaders.sqlite import SEED_PATH_ENV
from evaluation_harness import EvaluationVerdict
from tests.e2e.core.assessment_bindings import Scn06Witness, Scn07Witness, Scn08Witness
from tests.e2e.core.full_suite_adapters import run_canonical_full_suite

SEED_VALUE = os.environ.get(SEED_PATH_ENV)
pytestmark = pytest.mark.skipif(
    SEED_VALUE is None, reason=f"{SEED_PATH_ENV} is not configured"
)
REPORT_DIRECTORY = Path("docs/development")
EXPECTED_ASSERTIONS = (4, 5, 4, 3, 4, 5, 6, 6)


def test_canonical_suite_is_reproducible_over_two_fresh_sqlite_runtimes(
    tmp_path: Path,
) -> None:
    assert SEED_VALUE is not None
    seed_path = Path(SEED_VALUE)
    run_a = run_canonical_full_suite(seed_path, tmp_path / "g-run-a.sqlite")
    run_b = run_canonical_full_suite(seed_path, tmp_path / "g-run-b.sqlite")

    for run in (run_a, run_b):
        assert run.result.verdict is EvaluationVerdict.PASS
        assert run.result.infrastructure_error is False
        assert tuple(item.case_id.value for item in run.result.case_results) == tuple(
            f"case.scn-{index:02d}" for index in range(1, 9)
        )
        assert tuple(
            len(case.repetition_results[0].assertion_results)
            for case in run.result.case_results
        ) == EXPECTED_ASSERTIONS
        assert sum(EXPECTED_ASSERTIONS) == 37
        for case in run.result.case_results:
            repetition = case.repetition_results[0]
            assert repetition.verdict is EvaluationVerdict.PASS
            assert all(
                assertion.verdict is EvaluationVerdict.PASS
                for assertion in repetition.assertion_results
            )
            assert repetition.score_results == ()
            assert repetition.rubric_results == ()
        assert run.readiness.migration_applied is True
        assert run.readiness.documents_before == run.readiness.documents_after
        assert run.seed_before == run.seed_after == run.readiness.seed
        assert run.runtime_removed is True

    assert run_a.json_artifact.content == run_b.json_artifact.content
    assert run_a.markdown_artifact.content == run_b.markdown_artifact.content
    assert (
        REPORT_DIRECTORY / run_a.json_artifact.name.value
    ).read_bytes() == run_a.json_artifact.content
    assert (
        REPORT_DIRECTORY / run_a.markdown_artifact.name.value
    ).read_bytes() == run_a.markdown_artifact.content

    witnesses = run_a.witnesses
    assert witnesses.resource is not None
    assert witnesses.resource.route_count == witnesses.inbound_call_count == 1
    assert witnesses.resource.result.outcome.success is True
    assert witnesses.search is not None
    assert witnesses.search.retrieval.mode is RetrievalCoordinationMode.DEGRADED
    assert witnesses.search.materialized[0].item.source_ref == "notion:absence"

    generation = dict(witnesses.generation)
    assert generation["SCN-03"].generation.candidate.validation_state is (
        ProductionValidationState.CANDIDATE
    )
    assert generation["SCN-04"].evidence_set is not None
    assert generation["SCN-04"].evidence_set.evidence_items[0].source_ref == "notion:tva"
    assert generation["SCN-04"].events == ("AG-02:CAP-E01", "AG-03:CAP-G02")
    assert generation["SCN-05"].review_port_call_count == 1
    assert generation["SCN-05"].gate is not None
    assert generation["SCN-05"].gate.disposition is GateResolutionDisposition.APPROVED

    assessment = dict(witnesses.assessment)
    assert isinstance(assessment["SCN-06"], Scn06Witness)
    assert assessment["SCN-06"].events[-3:] == ("GENERATION", "VALIDATION", "REVIEW")
    assert isinstance(assessment["SCN-07"], Scn07Witness)
    assert assessment["SCN-07"].correction_result.new_production_ref.version_ref.value == "v2"
    assert assessment["SCN-07"].final_read.success is True
    assert isinstance(assessment["SCN-08"], Scn08Witness)
    assert len(assessment["SCN-08"].variants) == 2
    assert assessment["SCN-08"].gate_promotion.promotion is not None
    assert assessment["SCN-08"].gate_promotion.promotion.call_count == 1

    for raw_text in run_a.raw_texts:
        assert raw_text
        assert raw_text.encode("utf-8") not in run_a.json_artifact.content
        assert raw_text.encode("utf-8") not in run_a.markdown_artifact.content
