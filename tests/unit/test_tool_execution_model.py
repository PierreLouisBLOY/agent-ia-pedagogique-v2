from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentResultStatus,
    ContractMeta,
    InvocationStatus,
    PermissionScope,
    ToolCallRequest,
    ToolCallResult,
)
from backend.agent_runtime.policy import (
    ConditionalResolution,
    PermissionOperation,
    PolicyFacts,
    ToolCallPolicy,
)
from backend.agent_runtime.registry import BASELINE_TOOL_REGISTRY
from backend.agent_runtime.sandbox import (
    BASELINE_SANDBOX_PROFILE_REGISTRY,
    LOCAL_FILE_TRANSFORM_PROFILE_ID,
    ResolvedSandboxPath,
    SandboxOperation,
    SandboxPolicy,
    SandboxRelativePath,
    SandboxRootRef,
)
from backend.agent_runtime.tools import (
    PreparedToolExecution,
    SandboxOutputTarget,
    ToolExecutionOutcome,
    ToolExecutorBinding,
    ToolExecutorBindings,
    ToolRoutingContext,
    ToolRoutingError,
    ToolRoutingErrorCode,
    UnknownToolExecutorBindingError,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant
from tests.support.tool_execution_fakes import RecordingToolExecutor

NOW = Instant(datetime(2026, 8, 26, 14, 0, tzinfo=UTC))
BEFORE = Instant(NOW.value - timedelta(hours=1))
AFTER = Instant(NOW.value + timedelta(hours=1))
ROOT = SandboxRootRef(run_id="run-tool", root_id="sandbox-root")


def _request() -> ToolCallRequest:
    capability_id = CapabilityId("CAP-T02")
    actor = ActorRef(ActorKind.AGENT, AgentId.AG_01.value)
    return ToolCallRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-tool",
            "step-tool",
            None,
            CorrelationId("corr-tool"),
            NOW,
            actor,
            InvocationStatus.PLANNED,
        ),
        tool_id="tool.render_document",
        capability_id=capability_id,
        arguments={"source_ref": "artifact-input", "target_format": "pdf"},
        permission_scope=PermissionScope(
            principal=actor,
            capability_ids=(capability_id,),
            resource_scope={"artifact_refs": ("artifact-input",)},
            operations=(PermissionOperation.TRANSFORM.value,),
            constraints={"formats": ("pdf",)},
            valid_from=BEFORE,
            expires_at=AFTER,
            budget=None,
            delegable=False,
            gate_requirements=(),
            deny_rules=(),
        ),
        timeout=60,
        idempotency_key="idem-tool-1",
    )


def _resolved(
    path: SandboxRelativePath,
    *,
    exists: bool,
    mime_type: str | None,
) -> ResolvedSandboxPath:
    return ResolvedSandboxPath(
        root_ref=ROOT,
        relative_path=path,
        canonical_path_token=f"token-{path.value.replace('/', '-')}",
        exists=exists,
        is_file=exists,
        is_symlink=False,
        is_within_root=True,
        size_bytes=10 if exists else 0,
        observed_extension=path.extension,
        observed_mime_type=mime_type,
    )


def _prepared() -> PreparedToolExecution:
    request = _request()
    policy = ToolCallPolicy()
    tool_decision = policy.evaluate(
        agent_id=AgentId.AG_01,
        request=request,
        evaluated_at=NOW,
        facts=PolicyFacts(conditional_resolution=ConditionalResolution.ALLOW),
        declared_sandbox_profile_ids=(LOCAL_FILE_TRANSFORM_PROFILE_ID,),
    )
    profile = BASELINE_SANDBOX_PROFILE_REGISTRY.get(
        LOCAL_FILE_TRANSFORM_PROFILE_ID
    )
    sandbox_policy = SandboxPolicy()
    input_path = SandboxRelativePath("input/source.txt")
    output_target = SandboxOutputTarget(
        relative_path=SandboxRelativePath("output/result.pdf"),
        operation=SandboxOperation.CREATE,
        declared_output_bytes=100,
        declared_mime_type="application/pdf",
    )
    input_decision = sandbox_policy.evaluate(
        profile_id=profile.profile_id,
        root_ref=ROOT,
        operation=SandboxOperation.READ,
        relative_path=input_path,
        resolved_path=_resolved(input_path, exists=True, mime_type="text/plain"),
        file_count=2,
    )
    output_decision = sandbox_policy.evaluate(
        profile_id=profile.profile_id,
        root_ref=ROOT,
        operation=SandboxOperation.CREATE,
        relative_path=output_target.relative_path,
        resolved_path=_resolved(output_target.relative_path, exists=False, mime_type=None),
        file_count=2,
        declared_output_bytes=100,
        declared_mime_type="application/pdf",
    )
    descriptor = BASELINE_TOOL_REGISTRY.get(request.tool_id)
    return PreparedToolExecution(
        request=request,
        descriptor=descriptor,
        tool_decision=tool_decision,
        sandbox_profile=profile,
        root_ref=ROOT,
        input_paths=(input_path,),
        output_targets=(output_target,),
        input_sandbox_decisions=(input_decision,),
        output_sandbox_decisions=(output_decision,),
        effective_timeout=60,
        idempotency_key="idem-tool-1",
        run_id="run-tool",
        step_id="step-tool",
        correlation_id=CorrelationId("corr-tool"),
        input_contract_id=descriptor.input_contract_id,
        output_contract_id=descriptor.output_contract_id,
    )


def _result() -> ToolCallResult:
    request = _request()
    return ToolCallResult(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            request.meta.run_id,
            request.meta.step_id,
            None,
            request.meta.correlation_id,
            NOW,
            request.meta.actor,
            AgentResultStatus.SUCCEEDED,
        ),
        tool_id=request.tool_id,
        output={"rendered": True},
    )


def test_routing_context_is_typed_immutable_and_has_no_authority_override() -> None:
    context = ToolRoutingContext(
        root_ref=ROOT,
        input_paths=(SandboxRelativePath("input/source.txt"),),
        output_targets=(
            SandboxOutputTarget(
                SandboxRelativePath("output/result.pdf"),
                SandboxOperation.CREATE,
                100,
                "application/pdf",
            ),
        ),
    )

    assert {field.name for field in fields(ToolRoutingContext)} == {
        "root_ref",
        "input_paths",
        "output_targets",
    }
    with pytest.raises(FrozenInstanceError):
        context.root_ref = ROOT  # type: ignore[misc]


def test_routing_context_rejects_duplicate_or_missing_outputs() -> None:
    path = SandboxRelativePath("input/source.txt")
    with pytest.raises(ValueError, match="input_paths must be unique"):
        ToolRoutingContext(ROOT, (path, path), (_prepared().output_targets[0],))
    with pytest.raises(ValueError, match="output_targets must not be empty"):
        ToolRoutingContext(ROOT, (), ())


def test_output_target_rejects_read_and_invalid_size() -> None:
    path = SandboxRelativePath("output/result.pdf")
    with pytest.raises(ValueError, match="WRITE or CREATE"):
        SandboxOutputTarget(path, SandboxOperation.READ, 1, "application/pdf")
    with pytest.raises(ValueError, match=">= 0"):
        SandboxOutputTarget(path, SandboxOperation.CREATE, -1, "application/pdf")


def test_prepared_execution_binds_all_authorized_values_exactly() -> None:
    prepared = _prepared()

    assert prepared.request.tool_id == prepared.descriptor.tool_id
    assert prepared.tool_decision.tool_id == prepared.request.tool_id
    assert prepared.sandbox_profile.profile_id == LOCAL_FILE_TRANSFORM_PROFILE_ID
    assert prepared.effective_timeout == 60
    assert prepared.idempotency_key == "idem-tool-1"
    assert prepared.run_id == "run-tool"
    assert prepared.step_id == "step-tool"
    assert prepared.correlation_id == CorrelationId("corr-tool")


@pytest.mark.parametrize(
    "changes",
    [
        {"idempotency_key": "forged"},
        {"run_id": "other-run"},
        {"step_id": "other-step"},
        {"effective_timeout": 120},
        {"input_contract_id": "forged.contract"},
        {"input_sandbox_decisions": ()},
    ],
)
def test_prepared_execution_rejects_forged_or_incomplete_bindings(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        replace(_prepared(), **changes)


def test_execution_outcome_is_immutable_and_rejects_duplicate_paths() -> None:
    path = SandboxRelativePath("output/result.pdf")
    outcome = ToolExecutionOutcome(_result(), (path,))

    with pytest.raises(FrozenInstanceError):
        outcome.produced_paths = ()  # type: ignore[misc]
    with pytest.raises(ValueError, match="unique"):
        ToolExecutionOutcome(_result(), (path, path))


def test_executor_bindings_are_exact_distinct_and_fail_closed() -> None:
    executor = RecordingToolExecutor(
        ToolExecutionOutcome(
            _result(),
            (SandboxRelativePath("output/result.pdf"),),
        )
    )
    binding = ToolExecutorBinding("tool.render_document", executor)
    bindings = ToolExecutorBindings((binding,))

    assert bindings.get("tool.render_document") is executor
    assert bindings.contains("tool.render_document")
    assert not bindings.contains("tool.render")
    with pytest.raises(UnknownToolExecutorBindingError):
        bindings.get("tool.unknown")
    with pytest.raises(ValueError, match="duplicate"):
        ToolExecutorBindings((binding, binding))


def test_binding_contains_only_tool_id_and_executor() -> None:
    assert {field.name for field in fields(ToolExecutorBinding)} == {
        "tool_id",
        "executor",
    }


def test_routing_error_exposes_only_closed_code_and_safe_reason() -> None:
    error = ToolRoutingError(ToolRoutingErrorCode.OUTPUT_SANDBOX_DENIED)

    assert error.code is ToolRoutingErrorCode.OUTPUT_SANDBOX_DENIED
    assert error.safe_reason == "sandbox rejected a produced output"
    assert "output/result.pdf" not in str(error)
