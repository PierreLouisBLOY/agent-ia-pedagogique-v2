from __future__ import annotations

from decimal import Decimal

from calibration_tooling.contracts.errors import CalibrationErrorCode
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
from calibration_tooling.contracts.policy import DurableCalibrationPolicy
from calibration_tooling.runtime.authorization import ExecutionAuthorization
from calibration_tooling.runtime.budget import ApprovedBudget
from calibration_tooling.runtime.cli import (
    CalibrationCliExitCode,
    CalibrationCliInvocation,
    CalibrationCliReport,
    CalibrationCliStatus,
    main,
)
from calibration_tooling.runtime.composition import compose_calibration_runtime
from calibration_tooling.runtime.configuration import CalibrationRuntimeConfiguration


class ReportSink:
    reports: list[CalibrationCliReport]

    def __init__(self) -> None:
        self.reports = []

    def write(self, report: CalibrationCliReport) -> None:
        self.reports.append(report)


def _invocation() -> CalibrationCliInvocation:
    matrix = Sha256Digest("b" * 64)
    call_ref = CallRef("call.cli")
    plan = CalibrationPlan(
        CALIBRATION_SCHEMA_V1,
        RunRef("run.cli"),
        matrix,
        (
            AbsoluteObservationSpec(
                CALIBRATION_SCHEMA_V1,
                call_ref,
                CriterionRef("criterion.clarity"),
                ProjectionRef("projection.strong"),
                Decimal("0.010000"),
            ),
        ),
    )
    return CalibrationCliInvocation(
        plan=plan,
        authorization=ExecutionAuthorization(
            CALIBRATION_SCHEMA_V1,
            AuthorizationRef("auth.cli"),
            matrix,
            (call_ref,),
            1,
        ),
        budget=ApprovedBudget(CALIBRATION_SCHEMA_V1, Decimal("0.010000"), 1),
        policy=DurableCalibrationPolicy(),
    )


def test_runtime_configuration_is_live_disabled_by_default() -> None:
    configuration = CalibrationRuntimeConfiguration()
    assert configuration.live_provider_enabled is False
    assert configuration.anthropic is None
    assert "secret" not in repr(configuration).lower()


def test_cli_rejects_non_exact_command_without_ambient_resolution() -> None:
    output = ReportSink()
    exit_code = main(("unknown",), output=output)
    assert exit_code == int(CalibrationCliExitCode.CONFIGURATION_ERROR)
    assert output.reports == [
        CalibrationCliReport(
            status=CalibrationCliStatus.BLOCKED,
            run_ref=None,
            error_code=CalibrationErrorCode.CONFIGURATION_INVALID,
        )
    ]


def test_cli_reports_provider_disabled_without_composing_dependencies() -> None:
    invocation = _invocation()
    output = ReportSink()
    runtime = compose_calibration_runtime(
        configuration=CalibrationRuntimeConfiguration()
    )

    exit_code = main(
        ("run",), runtime=runtime, invocation=invocation, output=output
    )

    assert exit_code == int(CalibrationCliExitCode.EXECUTION_ERROR)
    assert output.reports == [
        CalibrationCliReport(
            status=CalibrationCliStatus.BLOCKED,
            run_ref=RunRef("run.cli"),
            error_code=CalibrationErrorCode.PROVIDER_DISABLED,
        )
    ]
