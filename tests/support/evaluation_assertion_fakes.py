from __future__ import annotations

from evaluation_harness import (
    EvaluationInvariantCode,
    EvaluationObservationRef,
    EvaluationObservationValue,
    InvariantCheckResult,
    InvariantNotFoundError,
    ObservationNotFoundError,
)


class RecordingObservationSource:
    def __init__(
        self,
        *entries: tuple[EvaluationObservationRef, EvaluationObservationValue],
        errors: tuple[tuple[EvaluationObservationRef, BaseException], ...] = (),
    ) -> None:
        refs = tuple(ref for ref, _ in entries)
        if len(refs) != len(set(refs)):
            raise ValueError("observation source refs must be unique")
        self._entries = entries
        self._errors = errors
        self.calls: list[EvaluationObservationRef] = []

    def resolve(
        self,
        observation_ref: EvaluationObservationRef,
    ) -> EvaluationObservationValue:
        self.calls.append(observation_ref)
        for error_ref, error in self._errors:
            if error_ref == observation_ref:
                raise error
        for candidate_ref, value in self._entries:
            if candidate_ref == observation_ref:
                return value
        raise ObservationNotFoundError


class RecordingInvariantEvaluator:
    def __init__(
        self,
        *entries: tuple[EvaluationInvariantCode, InvariantCheckResult],
        errors: tuple[tuple[EvaluationInvariantCode, BaseException], ...] = (),
    ) -> None:
        self._entries = entries
        self._errors = errors
        self.calls: list[
            tuple[EvaluationInvariantCode, EvaluationObservationValue]
        ] = []

    def evaluate(
        self,
        invariant_code: EvaluationInvariantCode,
        observation: EvaluationObservationValue,
    ) -> InvariantCheckResult:
        self.calls.append((invariant_code, observation))
        for error_code, error in self._errors:
            if error_code == invariant_code:
                raise error
        for candidate_code, result in self._entries:
            if candidate_code == invariant_code:
                return result
        raise InvariantNotFoundError
