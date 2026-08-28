"""Evaluation-harness adapter for canonical SCN-06, SCN-07 and SCN-08."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.agent_runtime.contracts import ProductionCandidate
from evaluation_harness import (
    EvaluationCaseCode,
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
    ObservationSequence,
    PreparedEvaluationInput,
    TargetExecutionOutcome,
    TargetExecutionStatus,
    TargetExecutorNotFoundError,
)
from tests.e2e.core.assessment_bindings import (
    Scn06Witness,
    Scn07Witness,
    Scn08Witness,
    candidate_is_bounded,
    candidate_sections,
    execute_scn06,
    execute_scn07,
    execute_scn08,
)
from tests.e2e.core.catalog import PEDAGOGICAL_INPUT_FACTORY_REF, scenario_for
from tests.e2e.core.fixtures import SyntheticPedagogicalFixture, fixture_for

_CASE_BY_ID = {
    "case.scn-06": EvaluationCaseCode("SCN-06"),
    "case.scn-07": EvaluationCaseCode("SCN-07"),
    "case.scn-08": EvaluationCaseCode("SCN-08"),
}
_TARGETS = frozenset(
    {"pedagogical.scn-06", "pedagogical.scn-07", "pedagogical.scn-08"}
)
_INVARIANTS = frozenset(
    {
        "pedagogical.scn-07.evidence-available",
        "pedagogical.scn-07.correction-version-increases",
        "pedagogical.scn-07.bounded-stop",
        "pedagogical.scn-08.independent-review",
    }
)


@dataclass(frozen=True, slots=True)
class EPreparedInput:
    case_code: EvaluationCaseCode
    level: str
    sections: tuple[str, ...]

    @property
    def evaluation_input_marker(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class EFixtureHandle:
    fixture: SyntheticPedagogicalFixture

    @property
    def evaluation_fixture_marker(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class FixedEvaluationClock:
    second: int

    def now_seconds(self) -> int:
        return self.second


class EInputFactory:
    def build(
        self,
        input_factory_ref: EvaluationInputFactoryRef,
        context: EvaluationRepetitionContext,
    ) -> PreparedEvaluationInput:
        if input_factory_ref != PEDAGOGICAL_INPUT_FACTORY_REF:
            raise InputFactoryNotFoundError(input_factory_ref.value)
        try:
            case_code = _CASE_BY_ID[context.case_id.value]
        except KeyError as error:
            raise InputFactoryNotFoundError(context.case_id.value) from error
        scenario = scenario_for(case_code)
        if scenario is None:
            raise InputFactoryNotFoundError(case_code.value)
        return EPreparedInput(
            case_code,
            scenario.level.value,
            tuple(section.value for section in scenario.section_codes),
        )


class EFixtureFactory:
    def create(
        self,
        fixture_ref: EvaluationFixtureRef,
        context: EvaluationRepetitionContext,
    ) -> EvaluationFixtureHandle:
        del context
        fixture = fixture_for(fixture_ref)
        if fixture is None:
            raise FixtureNotFoundError(fixture_ref.value)
        return EFixtureHandle(fixture)

    def cleanup(
        self,
        handle: EvaluationFixtureHandle,
        context: EvaluationRepetitionContext,
    ) -> None:
        del handle, context


class EInvariantEvaluator:
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


class EAssessmentTargetExecutor:
    def __init__(self) -> None:
        self.witnesses: dict[str, Scn06Witness | Scn07Witness | Scn08Witness] = {}
        self.raw_texts: list[str] = []

    def execute(
        self,
        target: EvaluationTargetRef,
        prepared_input: PreparedEvaluationInput,
        fixture: EvaluationFixtureHandle | None,
        context: EvaluationRepetitionContext,
        deadline: EvaluationDeadline,
    ) -> TargetExecutionOutcome:
        del context, deadline
        if target.code.value not in _TARGETS:
            raise TargetExecutorNotFoundError(target.code.value)
        if type(prepared_input) is not EPreparedInput:
            raise TypeError("E scenarios require EPreparedInput")
        if type(fixture) is not EFixtureHandle:
            raise TypeError("E scenarios require their declared fixture")
        self.raw_texts.extend(source.text for source in fixture.fixture.sources)
        code = prepared_input.case_code.value
        if code == "SCN-06":
            witness06 = execute_scn06(fixture.fixture)
            snapshot = _scn06_snapshot(prepared_input, witness06)
            self.raw_texts.extend(branch.raw_text for branch in witness06.evidence)
            _collect_candidate_text(self.raw_texts, witness06.generation.candidate)
            self.witnesses[code] = witness06
        elif code == "SCN-07":
            witness07 = execute_scn07(fixture.fixture)
            snapshot = _scn07_snapshot(witness07)
            self.raw_texts.append(witness07.evidence.raw_text)
            _collect_candidate_text(self.raw_texts, witness07.candidate)
            self.witnesses[code] = witness07
        else:
            witness08 = execute_scn08(fixture.fixture)
            snapshot = _scn08_snapshot(witness08)
            for variant in witness08.variants:
                _collect_candidate_text(self.raw_texts, variant.candidate)
            self.witnesses[code] = witness08
        return TargetExecutionOutcome(
            TargetExecutionStatus.COMPLETED,
            snapshot,
            duration_milliseconds=1,
        )


def _scn06_snapshot(
    prepared: EPreparedInput,
    witness: Scn06Witness,
) -> EvaluationObservationSnapshot:
    joined_refs = tuple(
        item.evidence_id
        for branch in witness.evidence
        for item in branch.evidence_set.evidence_items
    )
    structure = candidate_sections(witness.generation.candidate)
    structure_valid = (
        structure == prepared.sections
        and candidate_is_bounded(witness.generation.candidate, joined_refs)
    )
    return _snapshot(
        (
            ("scn-06.workflow", _string(witness.compiled.plan.workflow_kind)),
            ("scn-06.expected.workflow", _string("WF-8+WF-6")),
            ("scn-06.evidence-fanout-count", _integer(len(witness.evidence))),
            ("scn-06.expected.evidence-fanout-count.minimum", _integer(2)),
            (
                "scn-06.join-before-generation",
                _sequence(witness.events[:4]),
            ),
            (
                "scn-06.expected.join-before-generation",
                _sequence(("EVIDENCE_BRANCH_0", "EVIDENCE_BRANCH_1", "JOIN", "GENERATION")),
            ),
            (
                "scn-06.validation-review-order",
                _sequence(witness.events[3:]),
            ),
            (
                "scn-06.expected.validation-review-order",
                _sequence(("GENERATION", "VALIDATION", "REVIEW")),
            ),
            (
                "scn-06.assessment-marking-scheme",
                _sequence(structure if structure_valid else ()),
            ),
            (
                "scn-06.expected.assessment-marking-scheme",
                _sequence(prepared.sections),
            ),
        )
    )


def _scn07_snapshot(witness: Scn07Witness) -> EvaluationObservationSnapshot:
    parent = witness.correction_result.parent_production_ref
    new = witness.correction_result.new_production_ref
    version_increases = (
        parent.object_ref == new.object_ref
        and parent.version_ref.value == "v1"
        and new.version_ref.value == "v2"
        and witness.candidate.validation_state.value == "candidate"
        and witness.correction_result.addressed_findings
        == witness.correction_request.finding_ids
        and witness.correction_result.unresolved_findings == ()
    )
    route_code = (
        f"{witness.final_read.capability_id}:"
        f"{witness.final_read.use_case_id}:{witness.final_read.call_count}"
    )
    return _snapshot(
        (
            ("scn-07.workflow", _string(witness.compiled.plan.workflow_kind)),
            ("scn-07.expected.workflow", _string("WF-1+WF-7+WF-0")),
            (
                "scn-07.evidence-available",
                _boolean(bool(witness.evidence.evidence_set.evidence_items)),
            ),
            ("scn-07.correction-version-increases", _boolean(version_increases)),
            (
                "scn-07.review-correction-order",
                _sequence(witness.events[1:4]),
            ),
            (
                "scn-07.expected.review-correction-order",
                _sequence(("PRIOR_REVIEW_FINDING_AVAILABLE", "CORRECTION", "RE_REVIEW")),
            ),
            (
                "scn-07.bounded-stop",
                _boolean(
                    witness.correction_count == 1
                    and witness.events[-1] == "STOP"
                    and witness.compiled.plan.plan_version == 1
                ),
            ),
            ("scn-07.final-application-path", _string(route_code)),
            (
                "scn-07.expected.final-application-path",
                _string("CAP-R02:application.read_production:1"),
            ),
        )
    )


def _scn08_snapshot(witness: Scn08Witness) -> EvaluationObservationSnapshot:
    selected = witness.variants[witness.selected_index].candidate
    review_target = witness.review.result.target_production_ref
    independent_review = (
        witness.review.port_call_count == 1
        and review_target.object_ref.entity_id.value == selected.production_id
        and witness.variants[0].candidate.production_id
        != witness.variants[1].candidate.production_id
    )
    return _snapshot(
        (
            ("scn-08.workflow", _string(witness.compiled.plan.workflow_kind)),
            ("scn-08.expected.workflow", _string("WF-9+WF-3+WF-11")),
            ("scn-08.variant-count", _integer(len(witness.variants))),
            ("scn-08.expected.variant-count.minimum", _integer(2)),
            ("scn-08.join-selection-order", _sequence(witness.events[:4])),
            (
                "scn-08.expected.join-selection-order",
                _sequence(("VARIANT_0", "VARIANT_1", "JOIN", "SELECTION")),
            ),
            ("scn-08.independent-review", _boolean(independent_review)),
            (
                "scn-08.validation-gate-promotion-order",
                _sequence(witness.gate_promotion.events),
            ),
            (
                "scn-08.expected.validation-gate-promotion-order",
                _sequence(("VALIDATION", "GATE_APPROVED", "PROMOTION_REQUEST")),
            ),
            ("scn-08.render-effect-count", _integer(witness.render_effect_count)),
            ("scn-08.expected.render-effect-count.maximum", _integer(0)),
        )
    )


def _collect_candidate_text(target: list[str], candidate: ProductionCandidate) -> None:
    if candidate.content is not None:
        target.append(candidate.content)
    sections = candidate.structured_payload.get("sections")
    if isinstance(sections, Mapping):
        target.extend(value for value in sections.values() if isinstance(value, str))


def _snapshot(
    values: tuple[
        tuple[str, ObservationScalar | ObservationSequence], ...
    ],
) -> EvaluationObservationSnapshot:
    return EvaluationObservationSnapshot(
        tuple(
            EvaluationObservationSnapshotEntry(EvaluationObservationRef(ref), value)
            for ref, value in values
        )
    )


def _sequence(values: tuple[str, ...]) -> ObservationSequence:
    return ObservationSequence(tuple(_string(value) for value in values))


def _string(value: str) -> ObservationScalar:
    return ObservationScalar(ObservationScalarKind.STRING, value)


def _boolean(value: bool) -> ObservationScalar:
    return ObservationScalar(ObservationScalarKind.BOOLEAN, value)


def _integer(value: int) -> ObservationScalar:
    return ObservationScalar(ObservationScalarKind.INTEGER, value)
