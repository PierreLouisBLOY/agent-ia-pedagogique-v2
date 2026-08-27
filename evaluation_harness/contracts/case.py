from __future__ import annotations

from dataclasses import dataclass

from evaluation_harness.contracts.identity import (
    MAX_ASSERTION_REFS_PER_CASE,
    MAX_REPEAT_COUNT,
    MAX_TIMEOUT_SECONDS,
    EvaluationAssertionRef,
    EvaluationCaseCode,
    EvaluationCaseId,
    EvaluationFixtureRef,
    EvaluationInputFactoryRef,
    EvaluationSchemaVersion,
    EvaluationTagCode,
    require_safe_title,
    require_supported_schema_version,
    require_unique_bounded_tags,
)
from evaluation_harness.contracts.target import EvaluationTargetRef


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """Bounded evaluation declaration; it performs no execution or assertion."""

    case_id: EvaluationCaseId
    schema_version: EvaluationSchemaVersion
    code: EvaluationCaseCode
    title: str
    target: EvaluationTargetRef
    input_factory_ref: EvaluationInputFactoryRef
    assertion_refs: tuple[EvaluationAssertionRef, ...]
    fixture_ref: EvaluationFixtureRef | None = None
    repeat_count: int = 1
    tags: tuple[EvaluationTagCode, ...] = ()
    timeout_seconds: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, EvaluationCaseId):
            raise TypeError("case_id must be an EvaluationCaseId")
        require_supported_schema_version(self.schema_version)
        if not isinstance(self.code, EvaluationCaseCode):
            raise TypeError("code must be an EvaluationCaseCode")
        require_safe_title(self.title)
        if not isinstance(self.target, EvaluationTargetRef):
            raise TypeError("target must be an EvaluationTargetRef")
        if not isinstance(self.input_factory_ref, EvaluationInputFactoryRef):
            raise TypeError("input_factory_ref must be an EvaluationInputFactoryRef")
        self._validate_assertion_refs()
        if self.fixture_ref is not None and not isinstance(
            self.fixture_ref, EvaluationFixtureRef
        ):
            raise TypeError("fixture_ref must be an EvaluationFixtureRef or None")
        if type(self.repeat_count) is not int:
            raise TypeError("repeat_count must be an integer")
        if not 1 <= self.repeat_count <= MAX_REPEAT_COUNT:
            raise ValueError("repeat_count exceeds the offline evaluation limit")
        require_unique_bounded_tags(self.tags)
        if self.timeout_seconds is not None:
            if type(self.timeout_seconds) is not int:
                raise TypeError("timeout_seconds must be an integer or None")
            if not 1 <= self.timeout_seconds <= MAX_TIMEOUT_SECONDS:
                raise ValueError("timeout_seconds exceeds the offline evaluation limit")

    def _validate_assertion_refs(self) -> None:
        if type(self.assertion_refs) is not tuple:
            raise TypeError("assertion_refs must be a tuple")
        if not self.assertion_refs:
            raise ValueError("an evaluation case requires at least one assertion ref")
        if len(self.assertion_refs) > MAX_ASSERTION_REFS_PER_CASE:
            raise ValueError("too many assertion refs for one evaluation case")
        if any(
            type(reference) is not EvaluationAssertionRef
            for reference in self.assertion_refs
        ):
            raise TypeError("assertion_refs must contain EvaluationAssertionRef values")
        if len(self.assertion_refs) != len(set(self.assertion_refs)):
            raise ValueError("assertion refs must be unique")
