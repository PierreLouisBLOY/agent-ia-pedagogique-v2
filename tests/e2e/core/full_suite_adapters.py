"""Test-only composition facade for the complete canonical pedagogical suite."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from backend.adapters.inbound.application import ResourceLibraryUseCaseInbound
from backend.adapters.outbound.persistence.migrations import (
    DatabaseEvidence,
    RuntimeProvisioningReport,
    inspect_database,
)
from backend.agent_runtime.agents.evidence import EvidenceAgent, RetrievalCoordinator
from backend.agent_runtime.application_routing import (
    BASELINE_USE_CASE_REGISTRY,
    UseCaseInboundBinding,
    UseCaseInboundBindings,
    UseCaseRouter,
)
from backend.agent_runtime.policy import CapabilityAuthorizationPolicy
from backend.infrastructure.composition.factories.sqlite import build_sqlite_runtime
from backend.infrastructure.config.schemas.sqlite import SQLiteDatabasePaths
from backend.modules.resource_library.application.queries import GetResourceQuery
from backend.shared_kernel.time import Instant
from evaluation_harness import (
    EvaluationArtifact,
    EvaluationArtifactFactory,
    EvaluationArtifactFormat,
    EvaluationArtifactName,
    EvaluationCaseRunConfiguration,
    EvaluationDeadline,
    EvaluationFixtureHandle,
    EvaluationFixtureRef,
    EvaluationInputFactoryRef,
    EvaluationInvariantCode,
    EvaluationRepetitionContext,
    EvaluationReportProjector,
    EvaluationRunner,
    EvaluationTargetRef,
    FixtureNotFoundError,
    InputFactoryNotFoundError,
    InvariantCheckResult,
    InvariantNotFoundError,
    PreparedEvaluationInput,
    SuiteEvaluationResult,
    TargetExecutionOutcome,
    TargetExecutorNotFoundError,
)
from tests.e2e.core.adapters import (
    C1ExecutionWitness,
    C1FixtureFactory,
    C1InputFactory,
    C1InvariantEvaluator,
    C1SQLiteTargetExecutor,
)
from tests.e2e.core.assessment_adapters import (
    EAssessmentTargetExecutor,
    EFixtureFactory,
    EInputFactory,
    EInvariantEvaluator,
)
from tests.e2e.core.assessment_bindings import Scn06Witness, Scn07Witness, Scn08Witness
from tests.e2e.core.catalog import CANONICAL_PEDAGOGICAL_SUITE
from tests.e2e.core.expectations import PEDAGOGICAL_ASSERTION_CATALOG
from tests.e2e.core.generation_adapters import (
    DFixtureFactory,
    DGenerationTargetExecutor,
    DInputFactory,
    DInvariantEvaluator,
    DScenarioWitness,
    build_d_executor,
)
from tests.e2e.core.resource_adapters import (
    C2ExecutionWitness,
    C2FixtureFactory,
    C2InputFactory,
    C2SQLiteTargetExecutor,
    CountingApplicationInbound,
    FixedEvaluationClock,
)

MIGRATION_PATH = Path("database/migrations/001_document_sha256_check.sql")
JSON_REPORT_NAME = "PHASE_12_15_G_CANONICAL_SUITE_REPORT.json"
MARKDOWN_REPORT_NAME = "PHASE_12_15_G_CANONICAL_SUITE_REPORT.md"
_NOW = Instant(datetime(2026, 8, 28, 14, 0, tzinfo=UTC))
_CASE_OWNERS = {
    "case.scn-01": "C2",
    "case.scn-02": "C1",
    "case.scn-03": "D",
    "case.scn-04": "D",
    "case.scn-05": "D",
    "case.scn-06": "E",
    "case.scn-07": "E",
    "case.scn-08": "E",
}
_TARGET_OWNERS = {
    "pedagogical.scn-01": "C2",
    "pedagogical.scn-02": "C1",
    "pedagogical.scn-03": "D",
    "pedagogical.scn-04": "D",
    "pedagogical.scn-05": "D",
    "pedagogical.scn-06": "E",
    "pedagogical.scn-07": "E",
    "pedagogical.scn-08": "E",
}


@dataclass(frozen=True, slots=True)
class CanonicalFullSuiteWitnesses:
    resource: C2ExecutionWitness | None
    search: C1ExecutionWitness | None
    generation: tuple[tuple[str, DScenarioWitness], ...]
    assessment: tuple[
        tuple[str, Scn06Witness | Scn07Witness | Scn08Witness], ...
    ]
    inbound_call_count: int


@dataclass(frozen=True, slots=True)
class CanonicalFullSuiteRun:
    result: SuiteEvaluationResult
    json_artifact: EvaluationArtifact
    markdown_artifact: EvaluationArtifact
    readiness: RuntimeProvisioningReport
    seed_before: DatabaseEvidence
    seed_after: DatabaseEvidence
    witnesses: CanonicalFullSuiteWitnesses
    raw_texts: tuple[str, ...]
    runtime_removed: bool


class CanonicalFullSuiteInputFactory:
    def __init__(self) -> None:
        self._owners = {
            "C2": C2InputFactory(),
            "C1": C1InputFactory(),
            "D": DInputFactory(),
            "E": EInputFactory(),
        }

    def build(
        self,
        input_factory_ref: EvaluationInputFactoryRef,
        context: EvaluationRepetitionContext,
    ) -> PreparedEvaluationInput:
        try:
            owner = _CASE_OWNERS[context.case_id.value]
        except KeyError as error:
            raise InputFactoryNotFoundError(context.case_id.value) from error
        return self._owners[owner].build(input_factory_ref, context)


class CanonicalFullSuiteFixtureFactory:
    def __init__(self) -> None:
        self._owners = {
            "C2": C2FixtureFactory(),
            "C1": C1FixtureFactory(),
            "D": DFixtureFactory(),
            "E": EFixtureFactory(),
        }

    def create(
        self,
        fixture_ref: EvaluationFixtureRef,
        context: EvaluationRepetitionContext,
    ) -> EvaluationFixtureHandle:
        try:
            owner = _CASE_OWNERS[context.case_id.value]
        except KeyError as error:
            raise FixtureNotFoundError(context.case_id.value) from error
        return self._owners[owner].create(fixture_ref, context)

    def cleanup(
        self,
        handle: EvaluationFixtureHandle,
        context: EvaluationRepetitionContext,
    ) -> None:
        try:
            owner = _CASE_OWNERS[context.case_id.value]
        except KeyError as error:
            raise FixtureNotFoundError(context.case_id.value) from error
        self._owners[owner].cleanup(handle, context)


class CanonicalFullSuiteInvariantEvaluator:
    def __init__(self) -> None:
        self._owners = {
            "pedagogical.scn-02.": C1InvariantEvaluator(),
            "pedagogical.scn-03.": DInvariantEvaluator(),
            "pedagogical.scn-04.": DInvariantEvaluator(),
            "pedagogical.scn-05.": DInvariantEvaluator(),
            "pedagogical.scn-06.": EInvariantEvaluator(),
            "pedagogical.scn-07.": EInvariantEvaluator(),
            "pedagogical.scn-08.": EInvariantEvaluator(),
        }

    def evaluate(
        self,
        invariant_code: EvaluationInvariantCode,
        observation: object,
    ) -> InvariantCheckResult:
        for prefix, owner in self._owners.items():
            if invariant_code.value.startswith(prefix):
                return owner.evaluate(invariant_code, observation)
        raise InvariantNotFoundError(invariant_code.value)


class CanonicalFullSuiteTargetExecutor:
    def __init__(
        self,
        c2: C2SQLiteTargetExecutor,
        c1: C1SQLiteTargetExecutor,
        d: DGenerationTargetExecutor,
        e: EAssessmentTargetExecutor,
    ) -> None:
        self._owners = {"C2": c2, "C1": c1, "D": d, "E": e}

    def execute(
        self,
        target: EvaluationTargetRef,
        prepared_input: PreparedEvaluationInput,
        fixture: EvaluationFixtureHandle | None,
        context: EvaluationRepetitionContext,
        deadline: EvaluationDeadline,
    ) -> TargetExecutionOutcome:
        try:
            owner = _TARGET_OWNERS[target.code.value]
        except KeyError as error:
            raise TargetExecutorNotFoundError(target.code.value) from error
        return self._owners[owner].execute(
            target, prepared_input, fixture, context, deadline
        )


class _EvidenceClock:
    def now(self) -> Instant:
        return _NOW


def run_canonical_full_suite(
    seed_path: Path,
    runtime_path: Path,
) -> CanonicalFullSuiteRun:
    """Run all eight scenarios once and remove every runtime SQLite file."""

    seed_before = inspect_database(seed_path, authenticate_seed=True)
    composition = build_sqlite_runtime(
        SQLiteDatabasePaths(seed_path, runtime_path), MIGRATION_PATH
    )
    resources = composition.resource_store()
    c1_search = composition.evidence_search()
    c1_content = composition.evidence_document_content(_EvidenceClock())
    d_search = composition.evidence_search()
    d_content = composition.evidence_document_content(_EvidenceClock())
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
    c2 = C2SQLiteTargetExecutor(router, inbound, _NOW)
    c1 = C1SQLiteTargetExecutor(
        EvidenceAgent(RetrievalCoordinator(c1_search), c1_content), _NOW
    )
    d = build_d_executor(
        EvidenceAgent(RetrievalCoordinator(d_search), d_content)
    )
    e = EAssessmentTargetExecutor()

    try:
        result = EvaluationRunner(
            input_factory=CanonicalFullSuiteInputFactory(),
            target_executor=CanonicalFullSuiteTargetExecutor(c2, c1, d, e),
            clock=FixedEvaluationClock(1_777_002_000),
            fixture_factory=CanonicalFullSuiteFixtureFactory(),
            invariant_evaluator=CanonicalFullSuiteInvariantEvaluator(),
        ).run_suite(
            CANONICAL_PEDAGOGICAL_SUITE,
            tuple(
                EvaluationCaseRunConfiguration(
                    case.case_id, PEDAGOGICAL_ASSERTION_CATALOG
                )
                for case in CANONICAL_PEDAGOGICAL_SUITE.cases
            ),
        )
        report = EvaluationReportProjector().project(
            CANONICAL_PEDAGOGICAL_SUITE, result
        )
        artifacts = EvaluationArtifactFactory()
        json_artifact = artifacts.create(
            report,
            EvaluationArtifactName(JSON_REPORT_NAME),
            EvaluationArtifactFormat.JSON,
        )
        markdown_artifact = artifacts.create(
            report,
            EvaluationArtifactName(MARKDOWN_REPORT_NAME),
            EvaluationArtifactFormat.MARKDOWN,
        )
        witnesses = CanonicalFullSuiteWitnesses(
            c2.last_witness,
            c1.last_witness,
            tuple(sorted(d.witnesses.items())),
            tuple(sorted(e.witnesses.items())),
            len(inbound.calls),
        )
        raw_texts = (*c1.raw_fragments, *d.raw_texts, *e.raw_texts)
    finally:
        resources.close()
        c1_search.close()
        c1_content.close()
        d_search.close()
        d_content.close()
        _remove_runtime_files(runtime_path)

    seed_after = inspect_database(seed_path, authenticate_seed=True)
    return CanonicalFullSuiteRun(
        result,
        json_artifact,
        markdown_artifact,
        composition.readiness,
        seed_before,
        seed_after,
        witnesses,
        tuple(raw_texts),
        not any(path.exists() for path in _runtime_files(runtime_path)),
    )


def _runtime_files(runtime_path: Path) -> tuple[Path, ...]:
    return (
        runtime_path.with_name(runtime_path.name + "-wal"),
        runtime_path.with_name(runtime_path.name + "-shm"),
        runtime_path,
    )


def _remove_runtime_files(runtime_path: Path) -> None:
    for attempt in range(20):
        try:
            for path in _runtime_files(runtime_path):
                path.unlink(missing_ok=True)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)
