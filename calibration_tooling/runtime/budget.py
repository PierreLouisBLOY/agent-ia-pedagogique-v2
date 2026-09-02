from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from calibration_tooling.contracts.errors import CalibrationErrorCode, fail_execution
from calibration_tooling.contracts.models import (
    CALIBRATION_SCHEMA_V1,
    CalibrationObservationSpec,
    CalibrationPlan,
    CalibrationSchemaVersion,
)


@dataclass(frozen=True, slots=True)
class ApprovedBudget:
    schema_version: CalibrationSchemaVersion
    ceiling_usd: Decimal
    maximum_call_count: int

    def __post_init__(self) -> None:
        if self.schema_version is not CALIBRATION_SCHEMA_V1:
            raise ValueError("budget schema version is not supported")
        _require_money(self.ceiling_usd, positive=True)
        if type(self.maximum_call_count) is not int or self.maximum_call_count <= 0:
            raise ValueError("maximum_call_count must be a positive integer")


class BudgetGuard:
    def validate_plan(self, plan: CalibrationPlan, budget: ApprovedBudget) -> None:
        if type(budget) is not ApprovedBudget:
            fail_execution(CalibrationErrorCode.BUDGET_EXCEEDED)
        if budget.schema_version is not plan.schema_version:
            fail_execution(CalibrationErrorCode.IDENTITY_MISMATCH)
        if len(plan.observations) > budget.maximum_call_count:
            fail_execution(CalibrationErrorCode.BUDGET_EXCEEDED)
        maximum = sum(
            (item.maximum_cost_usd for item in plan.observations),
            start=Decimal("0"),
        )
        if maximum > budget.ceiling_usd:
            fail_execution(CalibrationErrorCode.BUDGET_EXCEEDED)

    def authorize_next(
        self,
        spec: CalibrationObservationSpec,
        budget: ApprovedBudget,
        completed_call_count: int,
        measured_cost_usd: Decimal,
    ) -> None:
        if completed_call_count >= budget.maximum_call_count:
            fail_execution(CalibrationErrorCode.BUDGET_EXCEEDED)
        if measured_cost_usd + spec.maximum_cost_usd > budget.ceiling_usd:
            fail_execution(CalibrationErrorCode.BUDGET_EXCEEDED)

    def add_actual(
        self,
        spec: CalibrationObservationSpec,
        budget: ApprovedBudget,
        measured_cost_usd: Decimal,
        call_cost_usd: Decimal,
    ) -> Decimal:
        _require_money(call_cost_usd, positive=False)
        if call_cost_usd > spec.maximum_cost_usd:
            fail_execution(CalibrationErrorCode.BUDGET_EXCEEDED)
        updated = measured_cost_usd + call_cost_usd
        if updated > budget.ceiling_usd:
            fail_execution(CalibrationErrorCode.BUDGET_EXCEEDED)
        return updated


def _require_money(value: Decimal, *, positive: bool) -> None:
    if type(value) is not Decimal or not value.is_finite():
        raise TypeError("budget values must be finite Decimal instances")
    if value < 0 or (positive and value == 0):
        raise ValueError("budget value is outside the active limit")
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -6:
        raise ValueError("budget precision exceeds six decimal places")
