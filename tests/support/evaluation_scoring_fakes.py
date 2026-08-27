from __future__ import annotations

from evaluation_harness import (
    EvaluationObservationValue,
    EvaluationScorerRef,
    ScorerNotFoundError,
    ScorerOutcome,
)


class RecordingScorer:
    def __init__(
        self,
        *entries: tuple[EvaluationScorerRef, object],
        errors: tuple[tuple[EvaluationScorerRef, BaseException], ...] = (),
    ) -> None:
        refs = tuple(reference for reference, _ in entries)
        if len(refs) != len(set(refs)):
            raise ValueError("scorer refs must be unique")
        self._entries = entries
        self._errors = errors
        self.calls: list[
            tuple[EvaluationScorerRef, tuple[EvaluationObservationValue, ...]]
        ] = []

    def score(
        self,
        scorer_ref: EvaluationScorerRef,
        observations: tuple[EvaluationObservationValue, ...],
    ) -> ScorerOutcome:
        self.calls.append((scorer_ref, observations))
        for error_ref, error in self._errors:
            if error_ref == scorer_ref:
                raise error
        for candidate_ref, result in self._entries:
            if candidate_ref == scorer_ref:
                return result  # type: ignore[return-value]
        raise ScorerNotFoundError
