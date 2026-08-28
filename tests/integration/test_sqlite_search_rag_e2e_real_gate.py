from __future__ import annotations

import os
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence.migrations import inspect_database
from backend.agent_runtime.agents.evidence import (
    EvidenceAgent,
    RetrievalChannel,
    RetrievalCoordinationMode,
    RetrievalCoordinator,
)
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
from tests.e2e.core.adapters import (
    C1FixtureFactory,
    C1InputFactory,
    C1InvariantEvaluator,
    C1SQLiteTargetExecutor,
    FixedEvaluationClock,
)
from tests.e2e.core.catalog import CANONICAL_PEDAGOGICAL_SUITE, scenario_for
from tests.e2e.core.expectations import PEDAGOGICAL_ASSERTION_CATALOG

SEED_VALUE = os.environ.get(SEED_PATH_ENV)
pytestmark = pytest.mark.skipif(
    SEED_VALUE is None, reason=f"{SEED_PATH_ENV} is not configured"
)
MIGRATION = Path("database/migrations/001_document_sha256_check.sql")
NOW = Instant(datetime(2026, 8, 28, 9, 0, tzinfo=UTC))


class _Clock:
    def now(self) -> Instant:
        return NOW


def test_scn_02_runs_full_harness_over_fresh_migrated_sqlite(
    tmp_path: Path,
) -> None:
    assert SEED_VALUE is not None
    seed_path = Path(SEED_VALUE)
    seed_before = inspect_database(seed_path, authenticate_seed=True)
    runtime_path = tmp_path / "c1-runtime.sqlite"
    composition = build_sqlite_runtime(
        SQLiteDatabasePaths(seed_path, runtime_path), MIGRATION
    )
    search = composition.evidence_search()
    content = composition.evidence_document_content(_Clock())
    executor = C1SQLiteTargetExecutor(
        EvidenceAgent(RetrievalCoordinator(search), content), NOW
    )

    try:
        scenario = scenario_for(EvaluationCaseCode("SCN-02"))
        assert scenario is not None
        suite = replace(CANONICAL_PEDAGOGICAL_SUITE, cases=(scenario.case,))
        result = EvaluationRunner(
            input_factory=C1InputFactory(),
            target_executor=executor,
            clock=FixedEvaluationClock(1_777_000_000),
            fixture_factory=C1FixtureFactory(),
            invariant_evaluator=C1InvariantEvaluator(),
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
            EvaluationArtifactName("scn-02.json"),
            EvaluationArtifactFormat.JSON,
        )
        markdown_artifact = artifacts.create(
            report,
            EvaluationArtifactName("scn-02.md"),
            EvaluationArtifactFormat.MARKDOWN,
        )

        assert result.verdict is EvaluationVerdict.PASS
        repetition = result.case_results[0].repetition_results[0]
        assert len(repetition.assertion_results) == 5
        assert all(
            assertion.verdict is EvaluationVerdict.PASS
            for assertion in repetition.assertion_results
        )
        assert repetition.score_results == ()
        assert repetition.rubric_results == ()

        witness = executor.last_witness
        assert witness is not None
        assert witness.retrieval.mode is RetrievalCoordinationMode.DEGRADED
        assert witness.retrieval.unavailable_channels == (
            RetrievalChannel.RELATIONAL,
            RetrievalChannel.SEMANTIC,
        )
        assert len(witness.retrieval.ranked_candidates) == 3
        fused = witness.retrieval.ranked_candidates[0]
        assert tuple(fused.channel_ranks) == (
            RetrievalChannel.STRUCTURED,
            RetrievalChannel.LEXICAL,
        )
        assert fused.representative.source_ref == "notion:absence"
        assert fused.representative.locator.startswith("search-chunk:")
        assert fused.representative.version_or_checksum
        lexical_only = witness.retrieval.ranked_candidates[1:]
        assert all(
            tuple(candidate.channel_ranks) == (RetrievalChannel.LEXICAL,)
            and candidate.representative.channel is RetrievalChannel.LEXICAL
            for candidate in lexical_only
        )
        assert len(
            {
                candidate.representative.source_ref
                for candidate in witness.retrieval.ranked_candidates
            }
        ) == 3
        assert len(witness.materialized) == 3
        assert witness.materialized[0].item.locator == fused.representative.locator
        assert tuple(item.item.locator for item in witness.materialized) == tuple(
            candidate.representative.locator
            for candidate in witness.retrieval.ranked_candidates
        )
        assert witness.evidence_set.coverage["materialized_count"] == 3
        assert witness.security.document_instructions_authoritative is False
        assert witness.security.external_actions_allowed is False
        assert witness.security.links_followed is False

        assert executor.raw_fragments
        for fragment in executor.raw_fragments:
            assert fragment
            assert fragment.encode("utf-8") not in json_artifact.content
            assert fragment.encode("utf-8") not in markdown_artifact.content
        assert b"PASS" in json_artifact.content
        assert b"PASS" in markdown_artifact.content
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
