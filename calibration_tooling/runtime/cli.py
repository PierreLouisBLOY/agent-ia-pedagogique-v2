"""Single dependency-injected CLI entry point for active calibration."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import IntEnum, StrEnum
from typing import Final, Protocol

from calibration_tooling.contracts.errors import CalibrationError, CalibrationErrorCode
from calibration_tooling.contracts.models import CalibrationPlan, RunRef
from calibration_tooling.contracts.policy import DurableCalibrationPolicy
from calibration_tooling.runtime.authorization import ExecutionAuthorization
from calibration_tooling.runtime.budget import ApprovedBudget
from calibration_tooling.runtime.composition import CalibrationRuntime

ACTIVE_CLI_TARGET: Final = "calibration_tooling.runtime.cli.v1"


class CalibrationCliStatus(StrEnum):
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class CalibrationCliExitCode(IntEnum):
    SUCCESS = 0
    CONFIGURATION_ERROR = 2
    EXECUTION_ERROR = 3


@dataclass(frozen=True, slots=True)
class CalibrationCliInvocation:
    plan: CalibrationPlan = field(repr=False)
    authorization: ExecutionAuthorization = field(repr=False)
    budget: ApprovedBudget = field(repr=False)
    policy: DurableCalibrationPolicy = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.plan) is not CalibrationPlan:
            raise TypeError("plan must be a CalibrationPlan")
        if type(self.authorization) is not ExecutionAuthorization:
            raise TypeError("authorization must be an ExecutionAuthorization")
        if type(self.budget) is not ApprovedBudget:
            raise TypeError("budget must be an ApprovedBudget")
        if type(self.policy) is not DurableCalibrationPolicy:
            raise TypeError("policy must be a DurableCalibrationPolicy")


@dataclass(frozen=True, slots=True)
class CalibrationCliReport:
    status: CalibrationCliStatus
    run_ref: RunRef | None
    measured_cost_usd: Decimal | None = None
    error_code: CalibrationErrorCode | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, CalibrationCliStatus):
            raise TypeError("status must be a CalibrationCliStatus")
        if self.run_ref is not None and type(self.run_ref) is not RunRef:
            raise TypeError("run_ref must be a RunRef or None")
        if self.measured_cost_usd is not None:
            if (
                type(self.measured_cost_usd) is not Decimal
                or not self.measured_cost_usd.is_finite()
                or self.measured_cost_usd < 0
            ):
                raise TypeError("measured_cost_usd must be a finite non-negative Decimal")
        if self.status is CalibrationCliStatus.COMPLETED and (
            self.run_ref is None
            or self.measured_cost_usd is None
            or self.error_code is not None
        ):
            raise ValueError("completed report requires run ref and cost")
        if self.status is CalibrationCliStatus.BLOCKED and self.error_code is None:
            raise ValueError("blocked report requires a closed error")


class CalibrationCliOutput(Protocol):
    def write(self, report: CalibrationCliReport) -> None: ...


def main(
    argv: tuple[str, ...],
    *,
    runtime: CalibrationRuntime | None = None,
    invocation: CalibrationCliInvocation | None = None,
    output: CalibrationCliOutput | None = None,
) -> int:
    """Execute only an explicitly injected `run` command; read no ambient state."""

    if (
        type(argv) is not tuple
        or any(type(argument) is not str for argument in argv)
        or argv != ("run",)
        or runtime is None
        or invocation is None
        or output is None
    ):
        if output is not None:
            output.write(
                CalibrationCliReport(
                    status=CalibrationCliStatus.BLOCKED,
                    run_ref=invocation.plan.run_ref if invocation is not None else None,
                    error_code=CalibrationErrorCode.CONFIGURATION_INVALID,
                )
            )
        return int(CalibrationCliExitCode.CONFIGURATION_ERROR)
    try:
        result = runtime.run(
            invocation.plan,
            invocation.authorization,
            invocation.budget,
            invocation.policy,
        )
    except CalibrationError as error:
        output.write(
            CalibrationCliReport(
                status=CalibrationCliStatus.BLOCKED,
                run_ref=invocation.plan.run_ref,
                error_code=error.code,
            )
        )
        return int(CalibrationCliExitCode.EXECUTION_ERROR)
    output.write(
        CalibrationCliReport(
            status=CalibrationCliStatus.COMPLETED,
            run_ref=result.run_ref,
            measured_cost_usd=result.measured_cost_usd,
        )
    )
    return int(CalibrationCliExitCode.SUCCESS)
