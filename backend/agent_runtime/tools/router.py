from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.agent_runtime.contracts import (
    AgentId,
    AgentResultStatus,
    ContractMeta,
    ToolCallRequest,
    ToolCallResult,
)
from backend.agent_runtime.contracts.common import (
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.errors import ErrorEnvelope
from backend.agent_runtime.policy import (
    PolicyFacts,
    ToolCallDisposition,
    ToolCallPolicy,
)
from backend.agent_runtime.registry import (
    ToolEffectClass,
    UnknownToolError,
)
from backend.agent_runtime.sandbox import (
    ResolvedSandboxPath,
    SandboxDecision,
    SandboxDisposition,
    SandboxFilesystemPort,
    SandboxOperation,
    SandboxPolicy,
    SandboxRelativePath,
    UnknownSandboxProfileError,
)
from backend.agent_runtime.tools.model import (
    PreparedToolExecution,
    SandboxOutputTarget,
    ToolExecutionOutcome,
    ToolRoutingContext,
    ToolRoutingError,
    ToolRoutingErrorCode,
)
from backend.agent_runtime.tools.ports import (
    ToolExecutorBindings,
    UnknownToolExecutorBindingError,
)
from backend.shared_kernel.time import Instant

_ROUTABLE_TOOL_IDS = frozenset({"tool.render_document", "tool.convert_format"})
_DEFAULT_POLICY_FACTS = PolicyFacts()
_FORBIDDEN_RESULT_KEYS = frozenset(
    {
        "absolute_path",
        "api_key",
        "capability_id",
        "capability_override",
        "credential",
        "credentials",
        "gate_approval",
        "handler",
        "handler_path",
        "import_path",
        "permission_scope",
        "profile_id",
        "provider",
        "provider_config",
        "provider_credentials",
        "root_path",
        "root_ref",
        "sandbox_root",
        "sandbox_profile_id",
        "secret",
        "tool_id",
        "tool_override",
    }
)
_FORBIDDEN_RESULT_KEYS_COMPACT = frozenset(
    key.replace("_", "") for key in _FORBIDDEN_RESULT_KEYS
)


@dataclass(frozen=True, slots=True)
class ToolRouter:
    tool_call_policy: ToolCallPolicy
    sandbox_policy: SandboxPolicy
    filesystem: SandboxFilesystemPort
    executor_bindings: ToolExecutorBindings

    def __post_init__(self) -> None:
        if not isinstance(self.tool_call_policy, ToolCallPolicy):
            raise TypeError("tool_call_policy must be a ToolCallPolicy")
        if not isinstance(self.sandbox_policy, SandboxPolicy):
            raise TypeError("sandbox_policy must be a SandboxPolicy")
        if not isinstance(self.filesystem, SandboxFilesystemPort):
            raise TypeError("filesystem must implement SandboxFilesystemPort")
        if not isinstance(self.executor_bindings, ToolExecutorBindings):
            raise TypeError("executor_bindings must be ToolExecutorBindings")

    def route(
        self,
        *,
        agent_id: AgentId,
        request: ToolCallRequest,
        context: ToolRoutingContext,
        evaluated_at: Instant,
        facts: PolicyFacts = _DEFAULT_POLICY_FACTS,
        satisfied_gate_requirements: tuple[str, ...] = (),
        scope_revoked: bool = False,
    ) -> ToolCallResult:
        if not isinstance(agent_id, AgentId):
            raise TypeError("agent_id must be an AgentId")
        if not isinstance(request, ToolCallRequest):
            raise TypeError("request must be a ToolCallRequest")
        if not isinstance(evaluated_at, Instant):
            raise TypeError("evaluated_at must be an Instant")
        if not isinstance(facts, PolicyFacts):
            raise TypeError("facts must be PolicyFacts")

        available_profile_ids = tuple(
            profile.profile_id
            for profile in self.sandbox_policy.profile_registry.all()
        )
        tool_decision = self.tool_call_policy.evaluate(
            agent_id=agent_id,
            request=request,
            evaluated_at=evaluated_at,
            facts=facts,
            declared_sandbox_profile_ids=available_profile_ids,
            satisfied_gate_requirements=satisfied_gate_requirements,
            scope_revoked=scope_revoked,
        )
        if tool_decision.disposition is not ToolCallDisposition.ALLOW:
            raise ToolRoutingError(ToolRoutingErrorCode.TOOL_NOT_ALLOWED)
        if request.tool_id not in _ROUTABLE_TOOL_IDS:
            raise ToolRoutingError(ToolRoutingErrorCode.TOOL_NOT_ALLOWED)
        if type(context) is not ToolRoutingContext:
            raise ToolRoutingError(ToolRoutingErrorCode.INVALID_EXECUTION_OUTCOME)
        _validate_context(context)

        try:
            descriptor = self.tool_call_policy.tool_registry.get(request.tool_id)
        except UnknownToolError:
            raise ToolRoutingError(ToolRoutingErrorCode.TOOL_NOT_ALLOWED) from None
        if descriptor.effect_class is not ToolEffectClass.LOCAL_FILE_TRANSFORM:
            raise ToolRoutingError(ToolRoutingErrorCode.TOOL_NOT_ALLOWED)
        profile_id = tool_decision.sandbox_profile_id
        if profile_id is None:
            raise ToolRoutingError(ToolRoutingErrorCode.SANDBOX_PROFILE_REQUIRED)
        try:
            profile = self.sandbox_policy.profile_registry.get(profile_id)
        except UnknownSandboxProfileError:
            raise ToolRoutingError(ToolRoutingErrorCode.SANDBOX_PROFILE_REQUIRED) from None

        input_decisions = tuple(
            self._sandbox_preflight(
                profile_id=profile_id,
                context=context,
                relative_path=relative_path,
                operation=SandboxOperation.READ,
            )
            for relative_path in context.input_paths
        )
        output_decisions = tuple(
            self._sandbox_preflight(
                profile_id=profile_id,
                context=context,
                relative_path=target.relative_path,
                operation=target.operation,
                output_target=target,
            )
            for target in context.output_targets
        )

        try:
            executor = self.executor_bindings.get(request.tool_id)
        except UnknownToolExecutorBindingError:
            raise ToolRoutingError(ToolRoutingErrorCode.TOOL_NOT_BOUND) from None

        if tool_decision.effective_timeout is None or request.idempotency_key is None:
            raise ToolRoutingError(ToolRoutingErrorCode.INVALID_EXECUTION_OUTCOME)
        prepared = PreparedToolExecution(
            request=request,
            descriptor=descriptor,
            tool_decision=tool_decision,
            sandbox_profile=profile,
            root_ref=context.root_ref,
            input_paths=context.input_paths,
            output_targets=context.output_targets,
            input_sandbox_decisions=input_decisions,
            output_sandbox_decisions=output_decisions,
            effective_timeout=tool_decision.effective_timeout,
            idempotency_key=request.idempotency_key,
            run_id=request.meta.run_id,
            step_id=request.meta.step_id,
            correlation_id=request.meta.correlation_id,
            input_contract_id=descriptor.input_contract_id,
            output_contract_id=descriptor.output_contract_id,
        )
        try:
            outcome = executor.execute(execution=prepared)
        except Exception:
            raise ToolRoutingError(ToolRoutingErrorCode.EXECUTOR_FAILED) from None

        result = _validate_execution_outcome(request, context, outcome)
        self._post_validate_outputs(profile_id, context, outcome.produced_paths)
        return result

    def _sandbox_preflight(
        self,
        *,
        profile_id: str,
        context: ToolRoutingContext,
        relative_path: SandboxRelativePath,
        operation: SandboxOperation,
        output_target: SandboxOutputTarget | None = None,
    ) -> SandboxDecision:
        inspected = self._resolve_and_inspect(
            context=context,
            relative_path=relative_path,
            post_execution=False,
        )
        decision = self.sandbox_policy.evaluate(
            profile_id=profile_id,
            root_ref=context.root_ref,
            operation=operation,
            relative_path=relative_path,
            resolved_path=inspected,
            file_count=len(context.input_paths) + len(context.output_targets),
            declared_output_bytes=(
                output_target.declared_output_bytes
                if output_target is not None
                else None
            ),
            declared_mime_type=(
                output_target.declared_mime_type
                if output_target is not None
                else None
            ),
            declares_active_content=(
                output_target.declares_active_content
                if output_target is not None
                else False
            ),
            declares_executable_content=(
                output_target.declares_executable_content
                if output_target is not None
                else False
            ),
        )
        if decision.disposition is not SandboxDisposition.ALLOW:
            raise ToolRoutingError(ToolRoutingErrorCode.SANDBOX_DENIED)
        return decision

    def _resolve_and_inspect(
        self,
        *,
        context: ToolRoutingContext,
        relative_path: SandboxRelativePath,
        post_execution: bool,
    ) -> ResolvedSandboxPath:
        try:
            resolved = self.filesystem.resolve(
                root_ref=context.root_ref,
                relative_path=relative_path,
            )
            if type(resolved) is not ResolvedSandboxPath:
                raise TypeError("invalid resolution")
            inspected = self.filesystem.inspect(resolved_path=resolved)
            if type(inspected) is not ResolvedSandboxPath:
                raise TypeError("invalid inspection")
            return inspected
        except Exception:
            code = (
                ToolRoutingErrorCode.OUTPUT_SANDBOX_DENIED
                if post_execution
                else ToolRoutingErrorCode.SANDBOX_RESOLUTION_FAILED
            )
            raise ToolRoutingError(code) from None

    def _post_validate_outputs(
        self,
        profile_id: str,
        context: ToolRoutingContext,
        produced_paths: tuple[SandboxRelativePath, ...],
    ) -> None:
        targets = {
            target.relative_path: target for target in context.output_targets
        }
        for relative_path in produced_paths:
            inspected = self._resolve_and_inspect(
                context=context,
                relative_path=relative_path,
                post_execution=True,
            )
            decision = self.sandbox_policy.evaluate(
                profile_id=profile_id,
                root_ref=context.root_ref,
                operation=SandboxOperation.WRITE,
                relative_path=relative_path,
                resolved_path=inspected,
                file_count=len(context.input_paths) + len(context.output_targets),
                declared_output_bytes=inspected.size_bytes,
                declared_mime_type=inspected.observed_mime_type,
                declares_active_content=inspected.has_active_content,
                declares_executable_content=inspected.is_executable_content,
            )
            if (
                relative_path not in targets
                or decision.disposition is not SandboxDisposition.ALLOW
            ):
                raise ToolRoutingError(ToolRoutingErrorCode.OUTPUT_SANDBOX_DENIED)


def _validate_context(context: ToolRoutingContext) -> None:
    try:
        ToolRoutingContext(
            root_ref=context.root_ref,
            input_paths=context.input_paths,
            output_targets=context.output_targets,
        )
    except (AttributeError, TypeError, ValueError):
        raise ToolRoutingError(
            ToolRoutingErrorCode.INVALID_EXECUTION_OUTCOME
        ) from None


def _validate_execution_outcome(
    request: ToolCallRequest,
    context: ToolRoutingContext,
    outcome: object,
) -> ToolCallResult:
    if type(outcome) is not ToolExecutionOutcome:
        raise ToolRoutingError(ToolRoutingErrorCode.INVALID_EXECUTION_OUTCOME)
    try:
        result = outcome.result
        if type(result) is not ToolCallResult:
            raise ToolRoutingError(ToolRoutingErrorCode.INVALID_EXECUTION_OUTCOME)
        _validate_result_identity(request, result)
        result = _validate_result_contract(result)
        authorized_paths = tuple(
            target.relative_path for target in context.output_targets
        )
        if not set(outcome.produced_paths).issubset(authorized_paths):
            raise ToolRoutingError(ToolRoutingErrorCode.OUTPUT_PATH_MISMATCH)
        if (
            result.meta.status is AgentResultStatus.SUCCEEDED
            and outcome.produced_paths != authorized_paths
        ):
            raise ToolRoutingError(ToolRoutingErrorCode.OUTPUT_PATH_MISMATCH)
        return result
    except ToolRoutingError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise ToolRoutingError(ToolRoutingErrorCode.INVALID_EXECUTION_OUTCOME) from None


def _validate_result_identity(
    request: ToolCallRequest,
    result: ToolCallResult,
) -> None:
    if result.tool_id != request.tool_id:
        raise ToolRoutingError(ToolRoutingErrorCode.RESULT_TOOL_MISMATCH)
    if result.meta.run_id != request.meta.run_id:
        raise ToolRoutingError(ToolRoutingErrorCode.RESULT_RUN_MISMATCH)
    if result.meta.step_id != request.meta.step_id:
        raise ToolRoutingError(ToolRoutingErrorCode.RESULT_STEP_MISMATCH)
    if result.meta.correlation_id != request.meta.correlation_id:
        raise ToolRoutingError(ToolRoutingErrorCode.RESULT_CORRELATION_MISMATCH)


def _validate_result_contract(result: ToolCallResult) -> ToolCallResult:
    if type(result.meta) is not ContractMeta:
        raise TypeError("invalid result metadata")
    if type(result.meta.status) is not AgentResultStatus:
        raise TypeError("invalid result status")
    if result.meta.status is AgentResultStatus.FAILED and result.error is None:
        raise ValueError("failed result requires an error")
    if result.meta.status is AgentResultStatus.SUCCEEDED and result.error is not None:
        raise ValueError("successful result cannot mask an error")
    if result.error is not None:
        if type(result.error) is not ErrorEnvelope:
            raise TypeError("invalid result error")
        if result.error.step_id != result.meta.step_id:
            raise ValueError("error step mismatch")
    if result.output is not None:
        if not isinstance(result.output, Mapping):
            raise TypeError("invalid result output")
        freeze_agent_safe_mapping(result.output)
        if _mapping_contains_authority(result.output):
            raise ValueError("result output contains authority data")
    if not isinstance(result.metrics, Mapping):
        raise TypeError("invalid result metrics")
    freeze_agent_safe_mapping(result.metrics)
    if _mapping_contains_authority(result.metrics):
        raise ValueError("result metrics contain authority data")
    if not isinstance(result.artifacts, tuple):
        raise TypeError("invalid result artifacts")
    for artifact in result.artifacts:
        require_contract_ref(artifact, "artifact")
    validated_meta = ContractMeta(
        schema_version=result.meta.schema_version,
        run_id=result.meta.run_id,
        step_id=result.meta.step_id,
        parent_step_id=result.meta.parent_step_id,
        correlation_id=result.meta.correlation_id,
        created_at=result.meta.created_at,
        actor=result.meta.actor,
        status=result.meta.status,
        trace_flags=result.meta.trace_flags,
    )
    return ToolCallResult(
        meta=validated_meta,
        tool_id=result.tool_id,
        output=result.output,
        artifacts=result.artifacts,
        metrics=result.metrics,
        error=result.error,
    )


def _mapping_contains_authority(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = _normalize_key(key)
            if (
                normalized in _FORBIDDEN_RESULT_KEYS
                or normalized.replace("_", "") in _FORBIDDEN_RESULT_KEYS_COMPACT
                or _mapping_contains_authority(nested)
            ):
                return True
        return False
    if isinstance(value, tuple):
        return any(_mapping_contains_authority(item) for item in value)
    return False


def _normalize_key(key: str) -> str:
    characters: list[str] = []
    for character in key:
        if character.isupper() and characters and characters[-1] != "_":
            characters.append("_")
        characters.append(character.casefold() if character.isalnum() else "_")
    return "_".join(part for part in "".join(characters).split("_") if part)
