from __future__ import annotations

import os
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence.migrations import inspect_database
from backend.agent_runtime.agents.evidence import EvidenceAgent, RetrievalCoordinator
from backend.agent_runtime.contracts import ProductionValidationState
from backend.infrastructure.composition.factories.sqlite import build_sqlite_runtime
from backend.infrastructure.config.loaders.sqlite import SEED_PATH_ENV
from backend.infrastructure.config.schemas.sqlite import SQLiteDatabasePaths
from backend.shared_kernel.time import Instant
from evaluation_harness import (
    EvaluationArtifactFactory,
    EvaluationArtifactFormat,
    EvaluationArtifactName,
    EvaluationCaseCode,
    EvaluationCaseRunConfiguration,
    EvaluationReportProjector,
    EvaluationRunner,
    EvaluationVerdict,
)
from tests.e2e.core.catalog import CANONICAL_PEDAGOGICAL_SUITE, scenario_for
from tests.e2e.core.expectations import PEDAGOGICAL_ASSERTION_CATALOG
from tests.e2e.core.generation_adapters import (
    SCN04_TARGET_REF,
    DFixtureFactory,
    DInputFactory,
    DInvariantEvaluator,
    FixedEvaluationClock,
    build_d_executor,
)

SEED_VALUE = os.environ.get(SEED_PATH_ENV)
pytestmark = pytest.mark.skipif(
    SEED_VALUE is None, reason=f"{SEED_PATH_ENV} is not configured"
)
MIGRATION = Path("database/migrations/001_document_sha256_check.sql")
NOW = Instant(datetime(2026, 8, 28, 13, 0, tzinfo=UTC))


class _Clock:
    def now(self) -> Instant:
        return NOW


def test_scn_04_runs_real_sqlite_evidence_before_real_transformation_owner(
    tmp_path: Path,
) -> None:
    assert SEED_VALUE is not None
    seed_path = Path(SEED_VALUE)
    seed_before = inspect_database(seed_path, authenticate_seed=True)
    runtime_path = tmp_path / "d-scn04-runtime.sqlite"
    composition = build_sqlite_runtime(
        SQLiteDatabasePaths(seed_path, runtime_path), MIGRATION
    )
    search = composition.evidence_search()
    content = composition.evidence_document_content(_Clock())
    executor = build_d_executor(
        EvidenceAgent(RetrievalCoordinator(search), content)
    )

    try:
        scenario = scenario_for(EvaluationCaseCode("SCN-04"))
        assert scenario is not None
        suite = replace(CANONICAL_PEDAGOGICAL_SUITE, cases=(scenario.case,))
        result = EvaluationRunner(
            input_factory=DInputFactory(),
            target_executor=executor,
            clock=FixedEvaluationClock(1_777_001_100),
            fixture_factory=DFixtureFactory(),
            invariant_evaluator=DInvariantEvaluator(),
        ).run_suite(
            suite,
            (
                EvaluationCaseRunConfiguration(
                    scenario.case.case_id, PEDAGOGICAL_ASSERTION_CATALOG
                ),
            ),
        )
        report = EvaluationReportProjector().project(suite, result)
        artifacts = EvaluationArtifactFactory()
        json_artifact = artifacts.create(
            report,
            EvaluationArtifactName("scn-04.json"),
            EvaluationArtifactFormat.JSON,
        )
        markdown_artifact = artifacts.create(
            report,
            EvaluationArtifactName("scn-04.md"),
            EvaluationArtifactFormat.MARKDOWN,
        )

        assert result.verdict is EvaluationVerdict.PASS
        repetition = result.case_results[0].repetition_results[0]
        assert len(repetition.assertion_results) == 3
        assert all(
            assertion.verdict is EvaluationVerdict.PASS
            for assertion in repetition.assertion_results
        )
        assert repetition.score_results == ()
        assert repetition.rubric_results == ()

        witness = executor.witnesses["SCN-04"]
        assert witness.evidence_set is not None
        assert witness.evidence_set.evidence_items
        assert witness.evidence_set.evidence_items[0].source_ref == "notion:tva"
        assert witness.events == ("AG-02:CAP-E01", "AG-03:CAP-G02")
        assert witness.generation.port_call_count == 1
        assert witness.generation.request.target_ref == SCN04_TARGET_REF
        assert witness.generation.candidate.lineage["target_ref"] == SCN04_TARGET_REF
        assert witness.generation.candidate.lineage["generation_operation"] == (
            "TRANSFORM"
        )
        assert witness.generation.candidate.evidence_refs_used
        assert set(witness.generation.candidate.evidence_refs_used).issubset(
            item.evidence_id for item in witness.evidence_set.evidence_items
        )
        assert witness.generation.candidate.validation_state is (
            ProductionValidationState.CANDIDATE
        )
        assert witness.source_unchanged is True

        for raw_text in executor.raw_texts:
            assert raw_text
            assert raw_text.encode("utf-8") not in json_artifact.content
            assert raw_text.encode("utf-8") not in markdown_artifact.content
        assert b"PASS" in json_artifact.content
        assert b"PASS" in markdown_artifact.content
        assert composition.readiness.migration_applied is True
    finally:
        search.close()
        content.close()
        _remove_runtime_files(runtime_path)

    assert not runtime_path.exists()
    assert inspect_database(seed_path, authenticate_seed=True) == seed_before


def _remove_runtime_files(runtime_path: Path) -> None:
    paths = (
        runtime_path.with_name(runtime_path.name + "-wal"),
        runtime_path.with_name(runtime_path.name + "-shm"),
        runtime_path,
    )
    for attempt in range(20):
        try:
            for path in paths:
                path.unlink(missing_ok=True)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)
