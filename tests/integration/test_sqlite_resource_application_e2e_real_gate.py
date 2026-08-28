from __future__ import annotations

import os
import time
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.adapters.inbound.application import ResourceLibraryUseCaseInbound
from backend.adapters.outbound.persistence.migrations import inspect_database
from backend.agent_runtime.application_routing import (
    BASELINE_USE_CASE_REGISTRY,
    UseCaseInboundBinding,
    UseCaseInboundBindings,
    UseCaseRouter,
)
from backend.agent_runtime.policy import CapabilityAuthorizationPolicy
from backend.infrastructure.composition.factories.sqlite import build_sqlite_runtime
from backend.infrastructure.config.loaders.sqlite import SEED_PATH_ENV
from backend.infrastructure.config.schemas.sqlite import SQLiteDatabasePaths
from backend.modules.resource_library.application.queries import GetResourceQuery
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
from tests.e2e.core.resource_adapters import (
    SCN_01_RESOURCE_REF,
    C2FixtureFactory,
    C2InputFactory,
    C2SQLiteTargetExecutor,
    CountingApplicationInbound,
    FixedEvaluationClock,
)

SEED_VALUE = os.environ.get(SEED_PATH_ENV)
pytestmark = pytest.mark.skipif(
    SEED_VALUE is None, reason=f"{SEED_PATH_ENV} is not configured"
)
MIGRATION = Path("database/migrations/001_document_sha256_check.sql")
NOW = Instant(datetime(2026, 8, 28, 10, 0, tzinfo=UTC))


def test_scn_01_runs_full_harness_through_wf0_application_and_op03(
    tmp_path: Path,
) -> None:
    assert SEED_VALUE is not None
    seed_path = Path(SEED_VALUE)
    seed_before = inspect_database(seed_path, authenticate_seed=True)
    runtime_path = tmp_path / "c2-runtime.sqlite"
    composition = build_sqlite_runtime(
        SQLiteDatabasePaths(seed_path, runtime_path), MIGRATION
    )
    resources = composition.resource_store()
    inbound = CountingApplicationInbound(
        ResourceLibraryUseCaseInbound(GetResourceQuery(resources))
    )
    router = UseCaseRouter(
        CapabilityAuthorizationPolicy(),
        BASELINE_USE_CASE_REGISTRY,
        UseCaseInboundBindings(
            (UseCaseInboundBinding("application.read_canonical_resource", inbound),)
        ),
    )
    executor = C2SQLiteTargetExecutor(router, inbound, NOW)

    try:
        scenario = scenario_for(EvaluationCaseCode("SCN-01"))
        assert scenario is not None
        suite = replace(CANONICAL_PEDAGOGICAL_SUITE, cases=(scenario.case,))
        result = EvaluationRunner(
            input_factory=C2InputFactory(),
            target_executor=executor,
            clock=FixedEvaluationClock(1_777_000_100),
            fixture_factory=C2FixtureFactory(),
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
            EvaluationArtifactName("scn-01.json"),
            EvaluationArtifactFormat.JSON,
        )
        markdown_artifact = artifacts.create(
            report,
            EvaluationArtifactName("scn-01.md"),
            EvaluationArtifactFormat.MARKDOWN,
        )

        assert result.verdict is EvaluationVerdict.PASS
        repetition = result.case_results[0].repetition_results[0]
        assert len(repetition.assertion_results) == 4
        assert all(
            assertion.verdict is EvaluationVerdict.PASS
            for assertion in repetition.assertion_results
        )
        assert repetition.score_results == ()
        assert repetition.rubric_results == ()

        witness = executor.last_witness
        assert witness is not None
        assert witness.route_count == 1
        assert len(inbound.calls) == 1
        assert inbound.calls[0] is witness.request
        assert witness.request.payload == {"resource_ref": SCN_01_RESOURCE_REF}
        assert witness.result.outcome.success is True
        assert isinstance(witness.result.outcome.data, Mapping)
        assert witness.result.outcome.data["resource_ref"] == SCN_01_RESOURCE_REF
        assert witness.result.outcome.data["resource_type"] == "EXERCISE_SET"
        assert witness.result.outcome.data["identity_status"] == "ACTIVE"

        title = witness.result.outcome.data["canonical_title"]
        assert type(title) is str and title
        assert title.encode("utf-8") not in json_artifact.content
        assert title.encode("utf-8") not in markdown_artifact.content
        assert b"PASS" in json_artifact.content
        assert b"PASS" in markdown_artifact.content
        assert composition.readiness.migration_applied is True
    finally:
        resources.close()
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
