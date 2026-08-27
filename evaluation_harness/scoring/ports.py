from __future__ import annotations

from typing import Protocol

from evaluation_harness.contracts.identity import EvaluationScorerRef
from evaluation_harness.contracts.observation import EvaluationObservationValue
from evaluation_harness.contracts.scoring import ScorerOutcome


class ScorerNotFoundError(LookupError):
    """Raw-value-free signal that an injected scorer does not own a ref."""


class EvaluationScorerPort(Protocol):
    def score(
        self,
        scorer_ref: EvaluationScorerRef,
        observations: tuple[EvaluationObservationValue, ...],
    ) -> ScorerOutcome: ...
