"""Public data-only contracts for the offline evaluation harness."""

from evaluation_harness.contracts.case import EvaluationCase
from evaluation_harness.contracts.identity import (
    EVALUATION_SCHEMA_V1_0,
    MAX_ASSERTION_REFS_PER_CASE,
    MAX_CASES_PER_SUITE,
    MAX_REPEAT_COUNT,
    MAX_TAGS,
    EvaluationAssertionRef,
    EvaluationCaseCode,
    EvaluationCaseId,
    EvaluationFixtureRef,
    EvaluationInputFactoryRef,
    EvaluationObservationRef,
    EvaluationReasonCode,
    EvaluationSchemaVersion,
    EvaluationSuiteCode,
    EvaluationSuiteId,
    EvaluationTagCode,
    EvaluationTargetCode,
)
from evaluation_harness.contracts.result import (
    CaseEvaluationResult,
    CaseExecutionResult,
    CaseExecutionStatus,
    SuiteEvaluationResult,
)
from evaluation_harness.contracts.suite import (
    EvaluationInfrastructureErrorPolicy,
    EvaluationSuite,
)
from evaluation_harness.contracts.target import (
    EvaluationTargetKind,
    EvaluationTargetRef,
)
from evaluation_harness.contracts.verdict import EvaluationVerdict

__all__ = [
    "EVALUATION_SCHEMA_V1_0",
    "MAX_ASSERTION_REFS_PER_CASE",
    "MAX_CASES_PER_SUITE",
    "MAX_REPEAT_COUNT",
    "MAX_TAGS",
    "CaseEvaluationResult",
    "CaseExecutionResult",
    "CaseExecutionStatus",
    "EvaluationAssertionRef",
    "EvaluationCase",
    "EvaluationCaseCode",
    "EvaluationCaseId",
    "EvaluationFixtureRef",
    "EvaluationInfrastructureErrorPolicy",
    "EvaluationInputFactoryRef",
    "EvaluationObservationRef",
    "EvaluationReasonCode",
    "EvaluationSchemaVersion",
    "EvaluationSuite",
    "EvaluationSuiteCode",
    "EvaluationSuiteId",
    "EvaluationTagCode",
    "EvaluationTargetCode",
    "EvaluationTargetKind",
    "EvaluationTargetRef",
    "EvaluationVerdict",
    "SuiteEvaluationResult",
]
