from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from evaluation_harness.assertions.ports import (
    EvaluationObservationSourcePort,
    InvariantCheckResult,
    InvariantEvaluatorPort,
    InvariantNotFoundError,
    ObservationNotFoundError,
)
from evaluation_harness.contracts.assertion import (
    AssertionReasonCode,
    AssertionResult,
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
from evaluation_harness.contracts.identity import EvaluationObservationRef
from evaluation_harness.contracts.observation import (
    EvaluationObservationValue,
    ObservationObject,
    ObservationScalar,
    ObservationScalarKind,
    ObservationSequence,
    validate_observation_value,
)
from evaluation_harness.contracts.verdict import EvaluationVerdict


class _ResolutionFailure(Exception):
    def __init__(self, reason_code: AssertionReasonCode) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code.value)


class AssertionEvaluator:
    """Pure single-assertion evaluator with explicitly injected boundaries."""

    def __init__(
        self,
        observation_source: EvaluationObservationSourcePort,
        invariant_evaluator: InvariantEvaluatorPort | None = None,
    ) -> None:
        self._observation_source = observation_source
        self._invariant_evaluator = invariant_evaluator

    def evaluate(self, spec: AssertionSpec) -> AssertionResult:
        cache: dict[EvaluationObservationRef, EvaluationObservationValue] = {}

        def resolve(reference: EvaluationObservationRef) -> EvaluationObservationValue:
            if reference in cache:
                return cache[reference]
            try:
                value = self._observation_source.resolve(reference)
            except ObservationNotFoundError:
                raise _ResolutionFailure(
                    AssertionReasonCode.OBSERVATION_NOT_FOUND
                ) from None
            except Exception:
                raise _ResolutionFailure(
                    AssertionReasonCode.OBSERVATION_RESOLUTION_ERROR
                ) from None
            try:
                validate_observation_value(value)
            except (TypeError, ValueError):
                raise _ResolutionFailure(
                    AssertionReasonCode.OBSERVATION_TYPE_UNSUPPORTED
                ) from None
            cache[reference] = value
            return value

        try:
            return self._evaluate_resolved(spec, resolve)
        except _ResolutionFailure as failure:
            return _result(
                spec,
                EvaluationVerdict.ERROR,
                failure.reason_code,
            )

    def _evaluate_resolved(
        self,
        spec: AssertionSpec,
        resolve: _ObservationResolver,
    ) -> AssertionResult:
        if type(spec) is ExactAssertionSpec:
            return _evaluate_exact(spec, resolve)
        if type(spec) is StructuralAssertionSpec:
            return _evaluate_structural(spec, resolve)
        if type(spec) is CountAssertionSpec:
            return _evaluate_count(spec, resolve)
        if type(spec) is SequenceAssertionSpec:
            return _evaluate_sequence(spec, resolve)
        if type(spec) is MembershipAssertionSpec:
            return _evaluate_membership(spec, resolve)
        if type(spec) is RangeAssertionSpec:
            return _evaluate_range(spec, resolve)
        if type(spec) is ForbiddenContentAssertionSpec:
            return _evaluate_forbidden_content(spec, resolve)
        if type(spec) is InvariantAssertionSpec:
            return self._evaluate_invariant(spec, resolve)
        raise TypeError("unsupported assertion spec")

    def _evaluate_invariant(
        self,
        spec: InvariantAssertionSpec,
        resolve: _ObservationResolver,
    ) -> AssertionResult:
        observation = resolve(spec.subject_ref)
        if self._invariant_evaluator is None:
            return _result(
                spec,
                EvaluationVerdict.ERROR,
                AssertionReasonCode.INVARIANT_NOT_FOUND,
            )
        try:
            outcome = self._invariant_evaluator.evaluate(
                spec.invariant_code,
                observation,
            )
        except InvariantNotFoundError:
            return _result(
                spec,
                EvaluationVerdict.ERROR,
                AssertionReasonCode.INVARIANT_NOT_FOUND,
            )
        except Exception:
            return _result(
                spec,
                EvaluationVerdict.ERROR,
                AssertionReasonCode.INVARIANT_EVALUATION_ERROR,
            )
        if type(outcome) is not InvariantCheckResult:
            return _result(
                spec,
                EvaluationVerdict.ERROR,
                AssertionReasonCode.INVARIANT_EVALUATION_ERROR,
            )
        reason = {
            EvaluationVerdict.PASS: None,
            EvaluationVerdict.FAIL: AssertionReasonCode.INVARIANT_FAILED,
            EvaluationVerdict.INCONCLUSIVE: AssertionReasonCode.INVARIANT_INCONCLUSIVE,
        }[outcome.verdict]
        return _result(spec, outcome.verdict, reason)


type _ObservationResolver = Callable[
    [EvaluationObservationRef], EvaluationObservationValue
]


def _evaluate_exact(
    spec: ExactAssertionSpec,
    resolve: _ObservationResolver,
) -> AssertionResult:
    subject = resolve(spec.subject_ref)
    expected = resolve(spec.expected_ref)
    passed = _canonical_equal(subject, expected)
    return _pass_or_fail(spec, passed, AssertionReasonCode.EXACT_MISMATCH)


def _evaluate_structural(
    spec: StructuralAssertionSpec,
    resolve: _ObservationResolver,
) -> AssertionResult:
    passed = _same_structure(resolve(spec.subject_ref), resolve(spec.expected_ref))
    return _pass_or_fail(spec, passed, AssertionReasonCode.STRUCTURE_MISMATCH)


def _evaluate_count(
    spec: CountAssertionSpec,
    resolve: _ObservationResolver,
) -> AssertionResult:
    subject = resolve(spec.subject_ref)
    if type(subject) is ObservationSequence:
        actual_count = len(subject.items)
    elif type(subject) is ObservationObject:
        actual_count = len(subject.fields)
    else:
        return _result(
            spec,
            EvaluationVerdict.ERROR,
            AssertionReasonCode.OBSERVATION_TYPE_UNSUPPORTED,
        )
    return _pass_or_fail(
        spec,
        actual_count == spec.expected_count,
        AssertionReasonCode.COUNT_MISMATCH,
    )


def _evaluate_sequence(
    spec: SequenceAssertionSpec,
    resolve: _ObservationResolver,
) -> AssertionResult:
    subject = resolve(spec.subject_ref)
    expected = resolve(spec.expected_ref)
    if type(subject) is not ObservationSequence or type(expected) is not ObservationSequence:
        return _result(
            spec,
            EvaluationVerdict.ERROR,
            AssertionReasonCode.OBSERVATION_TYPE_UNSUPPORTED,
        )
    return _pass_or_fail(
        spec,
        _canonical_equal(subject, expected),
        AssertionReasonCode.SEQUENCE_MISMATCH,
    )


def _evaluate_membership(
    spec: MembershipAssertionSpec,
    resolve: _ObservationResolver,
) -> AssertionResult:
    subject = resolve(spec.subject_ref)
    member = resolve(spec.member_ref)
    if type(subject) is not ObservationSequence:
        return _result(
            spec,
            EvaluationVerdict.ERROR,
            AssertionReasonCode.OBSERVATION_TYPE_UNSUPPORTED,
        )
    return _pass_or_fail(
        spec,
        any(_canonical_equal(item, member) for item in subject.items),
        AssertionReasonCode.MEMBERSHIP_MISMATCH,
    )


def _evaluate_range(
    spec: RangeAssertionSpec,
    resolve: _ObservationResolver,
) -> AssertionResult:
    subject = _numeric_value(resolve(spec.subject_ref))
    minimum = (
        _numeric_value(resolve(spec.minimum_ref))
        if spec.minimum_ref is not None
        else None
    )
    maximum = (
        _numeric_value(resolve(spec.maximum_ref))
        if spec.maximum_ref is not None
        else None
    )
    if subject is None or (spec.minimum_ref is not None and minimum is None) or (
        spec.maximum_ref is not None and maximum is None
    ):
        return _result(
            spec,
            EvaluationVerdict.ERROR,
            AssertionReasonCode.OBSERVATION_TYPE_UNSUPPORTED,
        )
    if minimum is not None and maximum is not None:
        if minimum > maximum or (
            minimum == maximum
            and (not spec.include_minimum or not spec.include_maximum)
        ):
            return _result(
                spec,
                EvaluationVerdict.ERROR,
                AssertionReasonCode.INVALID_ASSERTION_CONFIGURATION,
            )
    above_minimum = minimum is None or (
        subject >= minimum if spec.include_minimum else subject > minimum
    )
    below_maximum = maximum is None or (
        subject <= maximum if spec.include_maximum else subject < maximum
    )
    return _pass_or_fail(
        spec,
        above_minimum and below_maximum,
        AssertionReasonCode.RANGE_MISMATCH,
    )


def _evaluate_forbidden_content(
    spec: ForbiddenContentAssertionSpec,
    resolve: _ObservationResolver,
) -> AssertionResult:
    subject = _string_value(resolve(spec.subject_ref))
    patterns = tuple(_string_value(resolve(reference)) for reference in spec.forbidden_refs)
    if subject is None or any(pattern is None for pattern in patterns):
        return _result(
            spec,
            EvaluationVerdict.ERROR,
            AssertionReasonCode.OBSERVATION_TYPE_UNSUPPORTED,
        )
    if any(pattern == "" for pattern in patterns):
        return _result(
            spec,
            EvaluationVerdict.ERROR,
            AssertionReasonCode.INVALID_ASSERTION_CONFIGURATION,
        )
    comparable_subject = subject if spec.case_sensitive else subject.casefold()
    found = any(
        (pattern if spec.case_sensitive else pattern.casefold()) in comparable_subject
        for pattern in patterns
        if pattern is not None
    )
    return _pass_or_fail(
        spec,
        not found,
        AssertionReasonCode.FORBIDDEN_CONTENT_FOUND,
    )


def _canonical_equal(
    left: EvaluationObservationValue,
    right: EvaluationObservationValue,
) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is ObservationScalar and type(right) is ObservationScalar:
        return left.kind is right.kind and left.value == right.value
    if type(left) is ObservationSequence and type(right) is ObservationSequence:
        return len(left.items) == len(right.items) and all(
            _canonical_equal(left_item, right_item)
            for left_item, right_item in zip(left.items, right.items, strict=True)
        )
    if type(left) is ObservationObject and type(right) is ObservationObject:
        return len(left.fields) == len(right.fields) and all(
            left_field.code == right_field.code
            and _canonical_equal(left_field.value, right_field.value)
            for left_field, right_field in zip(left.fields, right.fields, strict=True)
        )
    return False


def _same_structure(
    left: EvaluationObservationValue,
    right: EvaluationObservationValue,
) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is ObservationScalar and type(right) is ObservationScalar:
        return left.kind is right.kind
    if type(left) is ObservationSequence and type(right) is ObservationSequence:
        return len(left.items) == len(right.items) and all(
            _same_structure(left_item, right_item)
            for left_item, right_item in zip(left.items, right.items, strict=True)
        )
    if type(left) is ObservationObject and type(right) is ObservationObject:
        return len(left.fields) == len(right.fields) and all(
            left_field.code == right_field.code
            and _same_structure(left_field.value, right_field.value)
            for left_field, right_field in zip(left.fields, right.fields, strict=True)
        )
    return False


def _numeric_value(value: EvaluationObservationValue) -> Decimal | None:
    if type(value) is not ObservationScalar:
        return None
    if value.kind is ObservationScalarKind.INTEGER:
        assert type(value.value) is int
        return Decimal(value.value)
    if value.kind is ObservationScalarKind.DECIMAL:
        assert type(value.value) is Decimal
        return value.value
    return None


def _string_value(value: EvaluationObservationValue) -> str | None:
    if type(value) is not ObservationScalar or value.kind is not ObservationScalarKind.STRING:
        return None
    assert type(value.value) is str
    return value.value


def _pass_or_fail(
    spec: AssertionSpec,
    passed: bool,
    failure_reason: AssertionReasonCode,
) -> AssertionResult:
    return _result(
        spec,
        EvaluationVerdict.PASS if passed else EvaluationVerdict.FAIL,
        None if passed else failure_reason,
    )


def _result(
    spec: AssertionSpec,
    verdict: EvaluationVerdict,
    reason_code: AssertionReasonCode | None,
) -> AssertionResult:
    return AssertionResult(
        schema_version=spec.schema_version,
        assertion_ref=spec.assertion_ref,
        kind=spec.kind,
        verdict=verdict,
        reason_code=reason_code,
    )
