from __future__ import annotations

from decimal import Decimal

import pytest

from calibration_tooling.contracts.errors import (
    CalibrationErrorCode,
    CalibrationExecutionError,
)
from calibration_tooling.contracts.models import (
    CALIBRATION_SCHEMA_V1,
    AbsoluteObservationSpec,
    AuthorizationRef,
    CalibrationPlan,
    CallRef,
    CriterionRef,
    ProjectionRef,
    RunRef,
    Sha256Digest,
)
from calibration_tooling.runtime.authorization import (
    ExecutionAuthorization,
    OneShotAuthorizationGuard,
)
from calibration_tooling.runtime.budget import ApprovedBudget, BudgetGuard

MATRIX = Sha256Digest("b" * 64)


def _spec(call_ref: str = "call.one", cost: str = "0.010000") -> AbsoluteObservationSpec:
    return AbsoluteObservationSpec(
        CALIBRATION_SCHEMA_V1,
        CallRef(call_ref),
        CriterionRef("criterion.clarity"),
        ProjectionRef("projection.strong"),
        Decimal(cost),
    )


def _plan(*specs: AbsoluteObservationSpec) -> CalibrationPlan:
    return CalibrationPlan(
        CALIBRATION_SCHEMA_V1,
        RunRef("run.authorization"),
        MATRIX,
        specs,
    )


def _authorization(plan: CalibrationPlan, ref: str = "auth.one") -> ExecutionAuthorization:
    calls = tuple(spec.call_ref for spec in plan.observations)
    return ExecutionAuthorization(
        CALIBRATION_SCHEMA_V1,
        AuthorizationRef(ref),
        MATRIX,
        calls,
        len(calls),
    )


def test_authorization_is_exact_and_consumed_before_execution() -> None:
    plan = _plan(_spec())
    authorization = _authorization(plan)
    guard = OneShotAuthorizationGuard()
    guard.consume(plan, authorization)
    assert guard.is_consumed(authorization.authorization_ref)
    with pytest.raises(CalibrationExecutionError) as captured:
        guard.consume(plan, authorization)
    assert captured.value.code is CalibrationErrorCode.AUTHORIZATION_CONSUMED


def test_authorization_rejects_non_exact_allowlist_and_matrix() -> None:
    plan = _plan(_spec())
    wrong_call = ExecutionAuthorization(
        CALIBRATION_SCHEMA_V1,
        AuthorizationRef("auth.wrong-call"),
        MATRIX,
        (CallRef("call.other"),),
        1,
    )
    with pytest.raises(CalibrationExecutionError) as captured:
        OneShotAuthorizationGuard().consume(plan, wrong_call)
    assert captured.value.code is CalibrationErrorCode.ALLOWLIST_MISMATCH

    wrong_matrix = ExecutionAuthorization(
        CALIBRATION_SCHEMA_V1,
        AuthorizationRef("auth.wrong-matrix"),
        Sha256Digest("c" * 64),
        (CallRef("call.one"),),
        1,
    )
    with pytest.raises(CalibrationExecutionError) as captured:
        OneShotAuthorizationGuard().consume(plan, wrong_matrix)
    assert captured.value.code is CalibrationErrorCode.IDENTITY_MISMATCH


def test_budget_requires_non_optional_exact_decimal_ceiling() -> None:
    budget = ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.030000"), 2)
    plan = _plan(_spec("call.one"), _spec("call.two", "0.020000"))
    guard = BudgetGuard()
    guard.validate_plan(plan, budget)
    guard.authorize_next(plan.observations[0], budget, 0, Decimal("0"))
    assert guard.add_actual(
        plan.observations[0], budget, Decimal("0"), Decimal("0.005000")
    ) == Decimal("0.005000")
    with pytest.raises(ValueError):
        ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.0000001"), 1)


def test_budget_rejects_plan_and_actual_cost_above_hard_limits() -> None:
    plan = _plan(_spec("call.one", "0.020000"), _spec("call.two", "0.020000"))
    budget = ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.030000"), 2)
    guard = BudgetGuard()
    with pytest.raises(CalibrationExecutionError) as captured:
        guard.validate_plan(plan, budget)
    assert captured.value.code is CalibrationErrorCode.BUDGET_EXCEEDED

    one = _spec(cost="0.010000")
    with pytest.raises(CalibrationExecutionError) as captured:
        guard.add_actual(one, budget, Decimal("0"), Decimal("0.010001"))
    assert captured.value.code is CalibrationErrorCode.BUDGET_EXCEEDED
