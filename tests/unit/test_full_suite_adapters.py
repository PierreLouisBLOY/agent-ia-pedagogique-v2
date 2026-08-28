from __future__ import annotations

from typing import cast

import pytest

from backend.agent_runtime.orchestration.workflows import WorkflowKind
from evaluation_harness import (
    EVALUATION_SCHEMA_V1_0,
    EvaluationCaseId,
    EvaluationInvariantCode,
    EvaluationRepetitionContext,
    EvaluationTargetCode,
    EvaluationTargetKind,
    EvaluationTargetRef,
    FixtureNotFoundError,
    InputFactoryNotFoundError,
    InvariantNotFoundError,
    ObservationScalar,
    ObservationScalarKind,
    TargetExecutorNotFoundError,
)
from tests.e2e.core.adapters import C1PreparedInput, C1SQLiteTargetExecutor
from tests.e2e.core.assessment_adapters import EAssessmentTargetExecutor, EPreparedInput
from tests.e2e.core.catalog import (
    CANONICAL_PEDAGOGICAL_SUITE,
    PEDAGOGICAL_INPUT_FACTORY_REF,
    workflow_coverage,
)
from tests.e2e.core.full_suite_adapters import (
    CanonicalFullSuiteFixtureFactory,
    CanonicalFullSuiteInputFactory,
    CanonicalFullSuiteInvariantEvaluator,
    CanonicalFullSuiteTargetExecutor,
)
from tests.e2e.core.generation_adapters import DGenerationTargetExecutor, DPreparedInput
from tests.e2e.core.resource_adapters import C2PreparedInput, C2SQLiteTargetExecutor


def _context(case_number: int) -> EvaluationRepetitionContext:
    return EvaluationRepetitionContext(
        EVALUATION_SCHEMA_V1_0,
        EvaluationCaseId(f"case.scn-{case_number:02d}"),
        1,
    )


def test_input_and_fixture_facades_delegate_in_canonical_case_order() -> None:
    inputs = CanonicalFullSuiteInputFactory()
    expected_types = (
        C2PreparedInput,
        C1PreparedInput,
        DPreparedInput,
        DPreparedInput,
        DPreparedInput,
        EPreparedInput,
        EPreparedInput,
        EPreparedInput,
    )

    for case, expected_type in zip(
        CANONICAL_PEDAGOGICAL_SUITE.cases, expected_types, strict=True
    ):
        context = EvaluationRepetitionContext(
            case.schema_version, case.case_id, 1
        )
        assert isinstance(
            inputs.build(PEDAGOGICAL_INPUT_FACTORY_REF, context), expected_type
        )
        fixture = CanonicalFullSuiteFixtureFactory()
        assert case.fixture_ref is not None
        handle = fixture.create(case.fixture_ref, context)
        fixture.cleanup(handle, context)


def test_composite_facades_fail_closed_for_unknown_owners() -> None:
    unknown = EvaluationRepetitionContext(
        EVALUATION_SCHEMA_V1_0, EvaluationCaseId("case.unknown"), 1
    )
    with pytest.raises(InputFactoryNotFoundError):
        CanonicalFullSuiteInputFactory().build(
            PEDAGOGICAL_INPUT_FACTORY_REF, unknown
        )
    with pytest.raises(FixtureNotFoundError):
        CanonicalFullSuiteFixtureFactory().create(
            CANONICAL_PEDAGOGICAL_SUITE.cases[0].fixture_ref, unknown  # type: ignore[arg-type]
        )
    with pytest.raises(InvariantNotFoundError):
        CanonicalFullSuiteInvariantEvaluator().evaluate(
            EvaluationInvariantCode("pedagogical.unknown.invariant"),
            ObservationScalar(ObservationScalarKind.BOOLEAN, True),
        )

    executor = CanonicalFullSuiteTargetExecutor(
        cast(C2SQLiteTargetExecutor, object()),
        cast(C1SQLiteTargetExecutor, object()),
        cast(DGenerationTargetExecutor, object()),
        cast(EAssessmentTargetExecutor, object()),
    )
    with pytest.raises(TargetExecutorNotFoundError):
        executor.execute(
            EvaluationTargetRef(
                EvaluationTargetKind.WORKFLOW,
                EvaluationTargetCode("pedagogical.unknown"),
            ),
            cast(C2PreparedInput, object()),
            None,
            _context(1),
            cast(object, object()),  # type: ignore[arg-type]
        )


def test_all_baseline_workflows_have_exact_scenario_traceability() -> None:
    assert workflow_coverage() == (
        (WorkflowKind.WF_0, (CANONICAL_PEDAGOGICAL_SUITE.cases[0].code, CANONICAL_PEDAGOGICAL_SUITE.cases[6].code)),
        (WorkflowKind.WF_1, (CANONICAL_PEDAGOGICAL_SUITE.cases[1].code, CANONICAL_PEDAGOGICAL_SUITE.cases[6].code)),
        (WorkflowKind.WF_2, (CANONICAL_PEDAGOGICAL_SUITE.cases[2].code,)),
        (WorkflowKind.WF_3, (CANONICAL_PEDAGOGICAL_SUITE.cases[7].code,)),
        (WorkflowKind.WF_4, (CANONICAL_PEDAGOGICAL_SUITE.cases[3].code,)),
        (WorkflowKind.WF_5, (CANONICAL_PEDAGOGICAL_SUITE.cases[4].code,)),
        (WorkflowKind.WF_6, (CANONICAL_PEDAGOGICAL_SUITE.cases[5].code,)),
        (WorkflowKind.WF_7, (CANONICAL_PEDAGOGICAL_SUITE.cases[6].code,)),
        (WorkflowKind.WF_8, (CANONICAL_PEDAGOGICAL_SUITE.cases[5].code,)),
        (WorkflowKind.WF_9, (CANONICAL_PEDAGOGICAL_SUITE.cases[7].code,)),
        (WorkflowKind.WF_10, (CANONICAL_PEDAGOGICAL_SUITE.cases[4].code,)),
        (WorkflowKind.WF_11, (CANONICAL_PEDAGOGICAL_SUITE.cases[7].code,)),
    )
