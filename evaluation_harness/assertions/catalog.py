from __future__ import annotations

from dataclasses import dataclass

from evaluation_harness.contracts.assertion import (
    MAX_ASSERTION_SPECS_PER_CATALOG,
    AssertionSpec,
    CountAssertionSpec,
    ExactAssertionSpec,
    ForbiddenContentAssertionSpec,
    InvariantAssertionSpec,
    MembershipAssertionSpec,
    RangeAssertionSpec,
    SequenceAssertionSpec,
    StructuralAssertionSpec,
)
from evaluation_harness.contracts.identity import EvaluationAssertionRef

_ASSERTION_SPEC_TYPES = (
    ExactAssertionSpec,
    StructuralAssertionSpec,
    CountAssertionSpec,
    SequenceAssertionSpec,
    MembershipAssertionSpec,
    RangeAssertionSpec,
    ForbiddenContentAssertionSpec,
    InvariantAssertionSpec,
)


@dataclass(frozen=True, slots=True)
class EvaluationAssertionCatalog:
    """Immutable offline configuration, never a process-global registry."""

    specs: tuple[AssertionSpec, ...]

    def __post_init__(self) -> None:
        if type(self.specs) is not tuple:
            raise TypeError("assertion catalog specs must be a tuple")
        if len(self.specs) > MAX_ASSERTION_SPECS_PER_CATALOG:
            raise ValueError("assertion catalog exceeds the offline limit")
        if any(type(spec) not in _ASSERTION_SPEC_TYPES for spec in self.specs):
            raise TypeError("assertion catalog contains an unsupported spec")
        refs = tuple(spec.assertion_ref for spec in self.specs)
        if len(refs) != len(set(refs)):
            raise ValueError("assertion catalog refs must be unique")

    def resolve(self, assertion_ref: EvaluationAssertionRef) -> AssertionSpec | None:
        if not isinstance(assertion_ref, EvaluationAssertionRef):
            raise TypeError("assertion_ref must be an EvaluationAssertionRef")
        return next(
            (spec for spec in self.specs if spec.assertion_ref == assertion_ref),
            None,
        )
