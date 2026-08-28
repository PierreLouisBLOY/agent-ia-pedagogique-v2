"""Test-only SCN-02 bindings from the golden corpus to the real AG-02 path."""

from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.agents.evidence import (
    EvidenceAgent,
    EvidenceCoverageStatus,
    EvidenceFetchRequest,
    EvidenceSecurityAssessment,
    EvidenceSecurityScanner,
    EvidenceSetBuildRequest,
    MaterializedEvidence,
    RetrievalCoordinationResult,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentResultStatus,
    ContractMeta,
    EvidenceRequest,
    EvidenceSet,
    InvocationStatus,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant
from evaluation_harness import (
    EvaluationDeadline,
    EvaluationFixtureHandle,
    EvaluationFixtureRef,
    EvaluationInputFactoryRef,
    EvaluationInvariantCode,
    EvaluationObservationRef,
    EvaluationObservationSnapshot,
    EvaluationObservationSnapshotEntry,
    EvaluationRepetitionContext,
    EvaluationTargetRef,
    EvaluationVerdict,
    FixtureNotFoundError,
    InputFactoryNotFoundError,
    InvariantCheckResult,
    InvariantNotFoundError,
    ObservationScalar,
    ObservationScalarKind,
    PreparedEvaluationInput,
    TargetExecutionOutcome,
    TargetExecutionStatus,
    TargetExecutorNotFoundError,
)
from tests.e2e.core.catalog import PEDAGOGICAL_INPUT_FACTORY_REF
from tests.e2e.core.fixtures import SyntheticPedagogicalFixture, fixture_for

_SCN_02_TARGET = "pedagogical.scn-02"
_SCN_02_QUERY = "absence"
_EVIDENCE_PATH = "AG02_SQLITE_OP11_OP13"
_INVARIANTS = frozenset(
    {
        "pedagogical.scn-02.provenance-valid",
        "pedagogical.scn-02.document-instruction-non-authoritative",
    }
)


@dataclass(frozen=True, slots=True)
class C1PreparedInput:
    query: str
    max_items: int

    @property
    def evaluation_input_marker(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class C1FixtureHandle:
    fixture: SyntheticPedagogicalFixture

    @property
    def evaluation_fixture_marker(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class C1ExecutionWitness:
    retrieval: RetrievalCoordinationResult
    materialized: tuple[MaterializedEvidence, ...]
    evidence_set: EvidenceSet
    security: EvidenceSecurityAssessment


@dataclass(frozen=True, slots=True)
class FixedEvaluationClock:
    second: int

    def now_seconds(self) -> int:
        return self.second


class C1InputFactory:
    def build(
        self,
        input_factory_ref: EvaluationInputFactoryRef,
        context: EvaluationRepetitionContext,
    ) -> PreparedEvaluationInput:
        del context
        if input_factory_ref != PEDAGOGICAL_INPUT_FACTORY_REF:
            raise InputFactoryNotFoundError(input_factory_ref.value)
        return C1PreparedInput(_SCN_02_QUERY, 3)


class C1FixtureFactory:
    def create(
        self,
        fixture_ref: EvaluationFixtureRef,
        context: EvaluationRepetitionContext,
    ) -> EvaluationFixtureHandle:
        del context
        fixture = fixture_for(fixture_ref)
        if fixture is None:
            raise FixtureNotFoundError(fixture_ref.value)
        return C1FixtureHandle(fixture)

    def cleanup(
        self,
        handle: EvaluationFixtureHandle,
        context: EvaluationRepetitionContext,
    ) -> None:
        del handle, context


class C1InvariantEvaluator:
    def evaluate(
        self,
        invariant_code: EvaluationInvariantCode,
        observation: object,
    ) -> InvariantCheckResult:
        if invariant_code.value not in _INVARIANTS:
            raise InvariantNotFoundError(invariant_code.value)
        passed = (
            type(observation) is ObservationScalar
            and observation.kind is ObservationScalarKind.BOOLEAN
            and observation.value is True
        )
        return InvariantCheckResult(
            EvaluationVerdict.PASS if passed else EvaluationVerdict.FAIL
        )


class C1SQLiteTargetExecutor:
    def __init__(self, agent: EvidenceAgent, now: Instant) -> None:
        self._agent = agent
        self._now = now
        self.last_witness: C1ExecutionWitness | None = None
        self.raw_fragments: tuple[str, ...] = ()

    def execute(
        self,
        target: EvaluationTargetRef,
        prepared_input: PreparedEvaluationInput,
        fixture: EvaluationFixtureHandle | None,
        context: EvaluationRepetitionContext,
        deadline: EvaluationDeadline,
    ) -> TargetExecutionOutcome:
        del deadline
        if target.code.value != _SCN_02_TARGET:
            raise TargetExecutorNotFoundError(target.code.value)
        if type(prepared_input) is not C1PreparedInput:
            raise TypeError("SCN-02 requires C1PreparedInput")
        if type(fixture) is not C1FixtureHandle:
            raise TypeError("SCN-02 requires its declared fixture")

        request = _evidence_request(prepared_input, context, self._now)
        retrieval = self._agent.search_evidence(request=request)
        materialized = tuple(
            self._agent.fetch_evidence_item(
                request=EvidenceFetchRequest(
                    evidence_id=f"evidence-{candidate.technical_rank}",
                    request=request,
                    retrieval=retrieval,
                    candidate=candidate,
                )
            )
            for candidate in retrieval.ranked_candidates
        )
        coverage = self._agent.assess_evidence_coverage(
            retrieval=retrieval, materialized=materialized
        )
        result_status = (
            AgentResultStatus.PARTIAL
            if coverage.status is EvidenceCoverageStatus.PARTIAL
            else AgentResultStatus.SUCCEEDED
        )
        evidence_set = self._agent.build_evidence_set(
            build_request=EvidenceSetBuildRequest(
                request=request,
                result_meta=_result_meta(request, result_status, self._now),
                retrieval=retrieval,
                materialized=materialized,
            )
        )
        security = EvidenceSecurityScanner().assess(evidence_set=evidence_set)
        self.raw_fragments = tuple(
            item.item.excerpt_or_summary or "" for item in materialized
        )
        self.last_witness = C1ExecutionWitness(
            retrieval, materialized, evidence_set, security
        )
        return TargetExecutionOutcome(
            TargetExecutionStatus.COMPLETED,
            _observations(
                materialized=materialized,
                security=security,
                maximum=prepared_input.max_items,
            ),
            duration_milliseconds=1,
        )


def _evidence_request(
    prepared: C1PreparedInput,
    context: EvaluationRepetitionContext,
    now: Instant,
) -> EvidenceRequest:
    suffix = f"{context.case_id.value}-{context.repetition_index}"
    return EvidenceRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id=f"run-{suffix}",
            step_id=f"step-{suffix}",
            parent_step_id=None,
            correlation_id=CorrelationId(f"corr-{suffix}"),
            created_at=now,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
            status=InvocationStatus.PLANNED,
        ),
        search_goal=prepared.query,
        scope={"level": "terminale-stmg"},
        source_policy={"kinds": ("canonical",)},
        filters={"active": True},
        required_authority=None,
        max_items=prepared.max_items,
    )


def _result_meta(
    request: EvidenceRequest,
    status: AgentResultStatus,
    now: Instant,
) -> ContractMeta[AgentResultStatus]:
    return ContractMeta(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        run_id=request.meta.run_id,
        step_id=request.meta.step_id,
        parent_step_id=request.meta.parent_step_id,
        correlation_id=request.meta.correlation_id,
        created_at=now,
        actor=ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
        status=status,
    )


def _observations(
    *,
    materialized: tuple[MaterializedEvidence, ...],
    security: EvidenceSecurityAssessment,
    maximum: int,
) -> EvaluationObservationSnapshot:
    provenance_valid = bool(materialized) and all(
        item.provenance.get("retrieval_candidate_provenance")
        and item.provenance.get("content_provenance")
        and item.item.checksum_or_version
        for item in materialized
    )
    values: tuple[tuple[str, ObservationScalar], ...] = (
        ("scn-02.workflow", _string("WF-1")),
        ("scn-02.expected.workflow", _string("WF-1")),
        ("scn-02.evidence-path", _string(_EVIDENCE_PATH)),
        ("scn-02.expected.evidence-path", _string(_EVIDENCE_PATH)),
        ("scn-02.provenance-valid", _boolean(provenance_valid)),
        ("scn-02.source-count", _integer(len(materialized))),
        ("scn-02.expected.source-count.minimum", _integer(1)),
        ("scn-02.expected.source-count.maximum", _integer(maximum)),
        (
            "scn-02.document-instruction-non-authoritative",
            _boolean(
                security.document_instructions_authoritative is False
                and security.external_actions_allowed is False
                and security.links_followed is False
            ),
        ),
    )
    return EvaluationObservationSnapshot(
        tuple(
            EvaluationObservationSnapshotEntry(EvaluationObservationRef(ref), value)
            for ref, value in values
        )
    )


def _string(value: str) -> ObservationScalar:
    return ObservationScalar(ObservationScalarKind.STRING, value)


def _boolean(value: bool) -> ObservationScalar:
    return ObservationScalar(ObservationScalarKind.BOOLEAN, value)


def _integer(value: int) -> ObservationScalar:
    return ObservationScalar(ObservationScalarKind.INTEGER, value)
