from __future__ import annotations

from decimal import Decimal
from typing import Final

from calibration_tooling.application.ports import CalibrationServicePort, CallLedgerPort
from calibration_tooling.contracts.errors import (
    CalibrationContractError,
    CalibrationErrorCode,
    CalibrationExecutionError,
    fail_execution,
)
from calibration_tooling.contracts.models import (
    AbsoluteObservationResult,
    AbsoluteObservationSpec,
    CalibrationPlan,
    CalibrationRunOutput,
    PairwiseObservationResult,
    PairwiseObservationSpec,
    RunStatus,
)
from calibration_tooling.contracts.policy import DurableCalibrationPolicy
from calibration_tooling.runtime.authorization import (
    ExecutionAuthorization,
    OneShotAuthorizationGuard,
)
from calibration_tooling.runtime.budget import ApprovedBudget, BudgetGuard

ACTIVE_RUNNER_TARGET: Final = "calibration_tooling.runtime.runner.v1"


class CanonicalCalibrationRunner:
    """The single active offline engine. It never retries or selects a provider."""

    def __init__(
        self,
        service: CalibrationServicePort,
        authorization_guard: OneShotAuthorizationGuard,
        budget_guard: BudgetGuard,
        ledger: CallLedgerPort,
    ) -> None:
        self._service = service
        self._authorization_guard = authorization_guard
        self._budget_guard = budget_guard
        self._ledger = ledger

    def run(
        self,
        plan: CalibrationPlan,
        authorization: ExecutionAuthorization,
        budget: ApprovedBudget,
        policy: DurableCalibrationPolicy,
    ) -> CalibrationRunOutput:
        if type(policy) is not DurableCalibrationPolicy:
            fail_execution(CalibrationErrorCode.INVALID_CONTRACT)
        self._budget_guard.validate_plan(plan, budget)
        self._authorization_guard.consume(plan, authorization)
        measured_cost = Decimal("0")
        results: list[AbsoluteObservationResult | PairwiseObservationResult] = []

        for spec in plan.observations:
            self._budget_guard.authorize_next(
                spec,
                budget,
                len(results),
                measured_cost,
            )
            self._ledger.reserve(spec.call_ref)
            try:
                scored_call = self._service.evaluate(spec)
            except CalibrationContractError as error:
                self._ledger.fail(spec.call_ref, error.code)
                raise
            except CalibrationExecutionError:
                raise
            if scored_call.result.call_ref != spec.call_ref:
                self._ledger.fail(
                    spec.call_ref,
                    CalibrationErrorCode.IDENTITY_MISMATCH,
                    scored_call.measured_cost_usd,
                )
                fail_execution(CalibrationErrorCode.IDENTITY_MISMATCH)
            if (
                type(spec) is AbsoluteObservationSpec
                and type(scored_call.result) is not AbsoluteObservationResult
                or type(spec) is PairwiseObservationSpec
                and type(scored_call.result) is not PairwiseObservationResult
            ):
                self._ledger.fail(
                    spec.call_ref,
                    CalibrationErrorCode.RESULT_MISMATCH,
                    scored_call.measured_cost_usd,
                )
                fail_execution(CalibrationErrorCode.RESULT_MISMATCH)
            try:
                measured_cost = self._budget_guard.add_actual(
                    spec,
                    budget,
                    measured_cost,
                    scored_call.measured_cost_usd,
                )
            except CalibrationExecutionError as error:
                self._ledger.fail(
                    spec.call_ref,
                    error.code,
                    scored_call.measured_cost_usd,
                )
                raise
            self._ledger.complete(scored_call.result, scored_call.measured_cost_usd)
            results.append(scored_call.result)

        return CalibrationRunOutput(
            schema_version=plan.schema_version,
            run_ref=plan.run_ref,
            status=RunStatus.COMPLETED,
            results=tuple(results),
            measured_cost_usd=measured_cost,
        )
