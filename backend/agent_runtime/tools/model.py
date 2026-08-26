from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from backend.agent_runtime.contracts import ToolCallRequest, ToolCallResult
from backend.agent_runtime.policy import (
    ToolCallDecision,
    ToolCallDisposition,
)
from backend.agent_runtime.registry import ToolDescriptor
from backend.agent_runtime.sandbox import (
    SandboxDecision,
    SandboxDisposition,
    SandboxOperation,
    SandboxProfile,
    SandboxRelativePath,
    SandboxRootRef,
)
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.correlation import CorrelationId


class ToolRoutingErrorCode(StrEnum):
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
    TOOL_NOT_BOUND = "TOOL_NOT_BOUND"
    SANDBOX_PROFILE_REQUIRED = "SANDBOX_PROFILE_REQUIRED"
    SANDBOX_RESOLUTION_FAILED = "SANDBOX_RESOLUTION_FAILED"
    SANDBOX_DENIED = "SANDBOX_DENIED"
    EXECUTOR_FAILED = "EXECUTOR_FAILED"
    RESULT_TOOL_MISMATCH = "RESULT_TOOL_MISMATCH"
    RESULT_RUN_MISMATCH = "RESULT_RUN_MISMATCH"
    RESULT_STEP_MISMATCH = "RESULT_STEP_MISMATCH"
    RESULT_CORRELATION_MISMATCH = "RESULT_CORRELATION_MISMATCH"
    OUTPUT_PATH_MISMATCH = "OUTPUT_PATH_MISMATCH"
    OUTPUT_SANDBOX_DENIED = "OUTPUT_SANDBOX_DENIED"
    INVALID_EXECUTION_OUTCOME = "INVALID_EXECUTION_OUTCOME"


_SAFE_REASONS = {
    ToolRoutingErrorCode.TOOL_NOT_ALLOWED: "tool call is not authorized",
    ToolRoutingErrorCode.TOOL_NOT_BOUND: "tool has no exact executor binding",
    ToolRoutingErrorCode.SANDBOX_PROFILE_REQUIRED: "sandbox profile is required",
    ToolRoutingErrorCode.SANDBOX_RESOLUTION_FAILED: "sandbox resolution failed",
    ToolRoutingErrorCode.SANDBOX_DENIED: "sandbox preflight denied the operation",
    ToolRoutingErrorCode.EXECUTOR_FAILED: "tool executor failed",
    ToolRoutingErrorCode.RESULT_TOOL_MISMATCH: "tool result identity mismatch",
    ToolRoutingErrorCode.RESULT_RUN_MISMATCH: "tool result run mismatch",
    ToolRoutingErrorCode.RESULT_STEP_MISMATCH: "tool result step mismatch",
    ToolRoutingErrorCode.RESULT_CORRELATION_MISMATCH: "tool result correlation mismatch",
    ToolRoutingErrorCode.OUTPUT_PATH_MISMATCH: "produced output paths are not authorized",
    ToolRoutingErrorCode.OUTPUT_SANDBOX_DENIED: "sandbox rejected a produced output",
    ToolRoutingErrorCode.INVALID_EXECUTION_OUTCOME: "executor returned an invalid outcome",
}


class ToolRoutingError(RuntimeError):
    code: ToolRoutingErrorCode
    safe_reason: str

    def __init__(self, code: ToolRoutingErrorCode) -> None:
        if not isinstance(code, ToolRoutingErrorCode):
            raise TypeError("code must be a ToolRoutingErrorCode")
        self.code = code
        self.safe_reason = _SAFE_REASONS[code]
        super().__init__(self.safe_reason)


@dataclass(frozen=True, slots=True)
class SandboxOutputTarget:
    relative_path: SandboxRelativePath
    operation: SandboxOperation
    declared_output_bytes: int
    declared_mime_type: str
    declares_active_content: bool = False
    declares_executable_content: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.relative_path, SandboxRelativePath):
            raise TypeError("relative_path must be a SandboxRelativePath")
        if self.operation not in {SandboxOperation.WRITE, SandboxOperation.CREATE}:
            raise ValueError("output operation must be WRITE or CREATE")
        if not isinstance(self.declared_output_bytes, int) or isinstance(
            self.declared_output_bytes, bool
        ):
            raise TypeError("declared_output_bytes must be an int")
        if self.declared_output_bytes < 0:
            raise ValueError("declared_output_bytes must be >= 0")
        require_non_empty(self.declared_mime_type, "declared_mime_type")
        if not isinstance(self.declares_active_content, bool):
            raise TypeError("declares_active_content must be a bool")
        if not isinstance(self.declares_executable_content, bool):
            raise TypeError("declares_executable_content must be a bool")


@dataclass(frozen=True, slots=True)
class ToolRoutingContext:
    root_ref: SandboxRootRef
    input_paths: tuple[SandboxRelativePath, ...]
    output_targets: tuple[SandboxOutputTarget, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.root_ref, SandboxRootRef):
            raise TypeError("root_ref must be a SandboxRootRef")
        _validate_exact_tuple(self.input_paths, SandboxRelativePath, "input_paths")
        _validate_exact_tuple(
            self.output_targets,
            SandboxOutputTarget,
            "output_targets",
        )
        if not self.output_targets:
            raise ValueError("output_targets must not be empty")
        input_values = tuple(path.value for path in self.input_paths)
        output_values = tuple(target.relative_path.value for target in self.output_targets)
        if len(input_values) != len(set(input_values)):
            raise ValueError("input_paths must be unique")
        if len(output_values) != len(set(output_values)):
            raise ValueError("output_targets must have unique paths")


@dataclass(frozen=True, slots=True)
class PreparedToolExecution:
    request: ToolCallRequest
    descriptor: ToolDescriptor
    tool_decision: ToolCallDecision
    sandbox_profile: SandboxProfile
    root_ref: SandboxRootRef
    input_paths: tuple[SandboxRelativePath, ...]
    output_targets: tuple[SandboxOutputTarget, ...]
    input_sandbox_decisions: tuple[SandboxDecision, ...]
    output_sandbox_decisions: tuple[SandboxDecision, ...]
    effective_timeout: int | float
    idempotency_key: str
    run_id: str
    step_id: str
    correlation_id: CorrelationId
    input_contract_id: str
    output_contract_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, ToolCallRequest):
            raise TypeError("request must be a ToolCallRequest")
        if not isinstance(self.descriptor, ToolDescriptor):
            raise TypeError("descriptor must be a ToolDescriptor")
        if not isinstance(self.tool_decision, ToolCallDecision):
            raise TypeError("tool_decision must be a ToolCallDecision")
        if self.tool_decision.disposition is not ToolCallDisposition.ALLOW:
            raise ValueError("tool_decision must be ALLOW")
        if not isinstance(self.sandbox_profile, SandboxProfile):
            raise TypeError("sandbox_profile must be a SandboxProfile")
        if not isinstance(self.root_ref, SandboxRootRef):
            raise TypeError("root_ref must be a SandboxRootRef")
        _validate_exact_tuple(self.input_paths, SandboxRelativePath, "input_paths")
        _validate_exact_tuple(
            self.output_targets,
            SandboxOutputTarget,
            "output_targets",
        )
        _validate_exact_tuple(
            self.input_sandbox_decisions,
            SandboxDecision,
            "input_sandbox_decisions",
        )
        _validate_exact_tuple(
            self.output_sandbox_decisions,
            SandboxDecision,
            "output_sandbox_decisions",
        )
        if len(self.input_paths) != len(self.input_sandbox_decisions):
            raise ValueError("each input path requires one sandbox decision")
        if len(self.output_targets) != len(self.output_sandbox_decisions):
            raise ValueError("each output target requires one sandbox decision")
        if not self.output_targets:
            raise ValueError("prepared execution requires an output target")
        if not isinstance(self.effective_timeout, (int, float)) or isinstance(
            self.effective_timeout, bool
        ):
            raise TypeError("effective_timeout must be a number")
        if self.effective_timeout < 0 or (
            isinstance(self.effective_timeout, float)
            and not isfinite(self.effective_timeout)
        ):
            raise ValueError("effective_timeout must be finite and >= 0")
        require_non_empty(self.idempotency_key, "idempotency_key")
        require_non_empty(self.run_id, "run_id")
        require_non_empty(self.step_id, "step_id")
        if not isinstance(self.correlation_id, CorrelationId):
            raise TypeError("correlation_id must be a CorrelationId")
        require_non_empty(self.input_contract_id, "input_contract_id")
        require_non_empty(self.output_contract_id, "output_contract_id")
        self._validate_exact_bindings()

    def _validate_exact_bindings(self) -> None:
        request = self.request
        descriptor = self.descriptor
        decision = self.tool_decision
        if (
            descriptor.tool_id != request.tool_id
            or descriptor.capability_id != request.capability_id
            or decision.tool_id != request.tool_id
            or decision.capability_id != request.capability_id
        ):
            raise ValueError("prepared tool identity must match the request")
        if (
            decision.sandbox_profile_id != self.sandbox_profile.profile_id
            or descriptor.sandbox_profile_id != self.sandbox_profile.profile_id
        ):
            raise ValueError("prepared sandbox profile must match descriptor and decision")
        if decision.effective_timeout != self.effective_timeout:
            raise ValueError("effective_timeout must match the tool decision")
        if request.idempotency_key != self.idempotency_key:
            raise ValueError("idempotency_key must match the request")
        if (
            request.meta.run_id != self.run_id
            or request.meta.step_id != self.step_id
            or request.meta.correlation_id != self.correlation_id
        ):
            raise ValueError("prepared execution metadata must match the request")
        if (
            descriptor.input_contract_id != self.input_contract_id
            or descriptor.output_contract_id != self.output_contract_id
        ):
            raise ValueError("contract IDs must match the descriptor")
        _validate_sandbox_decisions(
            self.input_sandbox_decisions,
            self.input_paths,
            self.root_ref,
            self.sandbox_profile.profile_id,
            SandboxOperation.READ,
        )
        _validate_sandbox_decisions(
            self.output_sandbox_decisions,
            tuple(target.relative_path for target in self.output_targets),
            self.root_ref,
            self.sandbox_profile.profile_id,
            None,
        )
        for target, sandbox_decision in zip(
            self.output_targets,
            self.output_sandbox_decisions,
            strict=True,
        ):
            if sandbox_decision.operation is not target.operation:
                raise ValueError("output sandbox operation must match its target")


@dataclass(frozen=True, slots=True)
class ToolExecutionOutcome:
    result: ToolCallResult
    produced_paths: tuple[SandboxRelativePath, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.result, ToolCallResult):
            raise TypeError("result must be a ToolCallResult")
        _validate_exact_tuple(
            self.produced_paths,
            SandboxRelativePath,
            "produced_paths",
        )
        path_values = tuple(path.value for path in self.produced_paths)
        if len(path_values) != len(set(path_values)):
            raise ValueError("produced_paths must be unique")


def _validate_exact_tuple(
    values: tuple[object, ...],
    item_type: type[object],
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    if any(type(value) is not item_type for value in values):
        raise TypeError(f"{field_name} contains an invalid value")


def _validate_sandbox_decisions(
    decisions: tuple[SandboxDecision, ...],
    paths: tuple[SandboxRelativePath, ...],
    root_ref: SandboxRootRef,
    profile_id: str,
    operation: SandboxOperation | None,
) -> None:
    for decision, path in zip(decisions, paths, strict=True):
        if (
            decision.disposition is not SandboxDisposition.ALLOW
            or decision.root_ref != root_ref
            or decision.profile_id != profile_id
            or decision.relative_path != path
            or (operation is not None and decision.operation is not operation)
        ):
            raise ValueError("prepared execution requires exact sandbox ALLOW decisions")
