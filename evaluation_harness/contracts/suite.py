from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from evaluation_harness.contracts.case import EvaluationCase
from evaluation_harness.contracts.identity import (
    MAX_CASES_PER_SUITE,
    EvaluationSchemaVersion,
    EvaluationSuiteCode,
    EvaluationSuiteId,
    EvaluationTagCode,
    require_safe_title,
    require_supported_schema_version,
    require_unique_bounded_tags,
)


class EvaluationInfrastructureErrorPolicy(Enum):
    CONTINUE = "CONTINUE"
    ABORT_SUITE = "ABORT_SUITE"


@dataclass(frozen=True, slots=True)
class EvaluationSuite:
    """Ordered, non-nested collection of embedded evaluation cases."""

    suite_id: EvaluationSuiteId
    schema_version: EvaluationSchemaVersion
    code: EvaluationSuiteCode
    title: str
    cases: tuple[EvaluationCase, ...]
    infrastructure_error_policy: EvaluationInfrastructureErrorPolicy = (
        EvaluationInfrastructureErrorPolicy.CONTINUE
    )
    tags: tuple[EvaluationTagCode, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.suite_id, EvaluationSuiteId):
            raise TypeError("suite_id must be an EvaluationSuiteId")
        require_supported_schema_version(self.schema_version)
        if not isinstance(self.code, EvaluationSuiteCode):
            raise TypeError("code must be an EvaluationSuiteCode")
        require_safe_title(self.title)
        self._validate_cases()
        if not isinstance(
            self.infrastructure_error_policy, EvaluationInfrastructureErrorPolicy
        ):
            raise TypeError(
                "infrastructure_error_policy must be an "
                "EvaluationInfrastructureErrorPolicy"
            )
        require_unique_bounded_tags(self.tags)

    def _validate_cases(self) -> None:
        if type(self.cases) is not tuple:
            raise TypeError("cases must be a tuple")
        if not self.cases:
            raise ValueError("an evaluation suite requires at least one case")
        if len(self.cases) > MAX_CASES_PER_SUITE:
            raise ValueError("too many cases for one evaluation suite")
        if any(type(case) is not EvaluationCase for case in self.cases):
            raise TypeError("cases must contain EvaluationCase values")
        case_ids = tuple(case.case_id for case in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("evaluation case IDs must be unique within a suite")
