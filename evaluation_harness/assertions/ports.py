from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from evaluation_harness.contracts.identity import (
    EvaluationInvariantCode,
    EvaluationObservationRef,
)
from evaluation_harness.contracts.observation import EvaluationObservationValue
from evaluation_harness.contracts.verdict import EvaluationVerdict


class ObservationNotFoundError(LookupError):
    """Raw-value-free signal that an injected source cannot resolve a ref."""


class InvariantNotFoundError(LookupError):
    """Raw-value-free signal that an injected checker does not own a code."""


@dataclass(frozen=True, slots=True)
class InvariantCheckResult:
    verdict: EvaluationVerdict

    def __post_init__(self) -> None:
        if self.verdict not in {
            EvaluationVerdict.PASS,
            EvaluationVerdict.FAIL,
            EvaluationVerdict.INCONCLUSIVE,
        }:
            raise ValueError(
                "an invariant checker returns PASS, FAIL, or INCONCLUSIVE"
            )


class EvaluationObservationSourcePort(Protocol):
    def resolve(
        self, observation_ref: EvaluationObservationRef
    ) -> EvaluationObservationValue: ...


class InvariantEvaluatorPort(Protocol):
    def evaluate(
        self,
        invariant_code: EvaluationInvariantCode,
        observation: EvaluationObservationValue,
    ) -> InvariantCheckResult: ...
