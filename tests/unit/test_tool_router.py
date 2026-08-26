from __future__ import annotations

from dataclasses import replace
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
from backend.agent_runtime.contracts.errors import (
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
)
from backend.agent_runtime.policy import (
    CapabilityAuthorizationPolicy,
    ConditionalResolution,
    PermissionOperation,
    PolicyFacts,
    ToolCallPolicy,
)
from backend.agent_runtime.registry import (
    BASELINE_TOOL_REGISTRY,
    ToolEffectClass,
    ToolRegistry,
)
from backend.agent_runtime.sandbox import (
    ResolvedSandboxPath,
    SandboxOperation,
    SandboxPolicy,
    SandboxProfileRegistry,
    SandboxRelativePath,
    SandboxRootRef,
)
from backend.agent_runtime.tools import (
    SandboxOutputTarget,
    ToolExecutionOutcome,
    ToolExecutorBinding,
    ToolExecutorBindings,
    ToolRouter,
    ToolRoutingContext,
    ToolRoutingError,
    ToolRoutingErrorCode,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant
from tests.support.tool_execution_fakes import (
    RecordingSandboxFilesystem,
    RecordingToolExecutor,
)

NOW = Instant(datetime(2026, 8, 26, 15, 0, tzinfo=UTC))
BEFORE = Instant(NOW.value - timedelta(hours=1))
AFTER = Instant(NOW.value + timedelta(hours=1))
ROOT = SandboxRootRef(run_id="run-router", root_id="root-router")
INPUT = SandboxRelativePath("input/source.txt")
OUTPUT = SandboxRelativePath("output/result.pdf")
CAP_T02 = CapabilityId("CAP-T02")


def _request(
    *,
    tool_id: str = "tool.render_document",
    capability_id: CapabilityId = CAP_T02,
    idempotency_key: str | None = "idem-router-1",
) -> ToolCallRequest:
    actor = ActorRef(ActorKind.AGENT, AgentId.AG_01.value)
    return ToolCallRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-router",
            "step-router",
            None,
            CorrelationId("corr-router"),
            NOW,
            actor,
            InvocationStatus.PLANNED,
        ),
        tool_id=tool_id,
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
        idempotency_key=idempotency_key,
    )


def _context(
    *,
    output_path: SandboxRelativePath = OUTPUT,
    operation: SandboxOperation = SandboxOperation.CREATE,
) -> ToolRoutingContext:
    return ToolRoutingContext(
        root_ref=ROOT,
        input_paths=(INPUT,),
        output_targets=(
            SandboxOutputTarget(
                relative_path=output_path,
                operation=operation,
                declared_output_bytes=100,
                declared_mime_type="application/pdf",
            ),
        ),
    )


def _resolved(
    path: SandboxRelativePath,
    *,
    root_ref: SandboxRootRef = ROOT,
    exists: bool,
    mime_type: str | None,
    size_bytes: int | None = None,
    **overrides: object,
) -> ResolvedSandboxPath:
    values: dict[str, object] = {
        "root_ref": root_ref,
        "relative_path": path,
        "canonical_path_token": f"token-{path.value.replace('/', '-')}",
        "exists": exists,
        "is_file": exists,
        "is_symlink": False,
        "is_within_root": True,
        "size_bytes": (10 if exists else 0) if size_bytes is None else size_bytes,
        "observed_extension": path.extension,
        "observed_mime_type": mime_type,
        "has_active_content": False,
        "is_executable_content": False,
    }
    values.update(overrides)
    return ResolvedSandboxPath(**values)  # type: ignore[arg-type]


def _result(
    request: ToolCallRequest,
    *,
    tool_id: str | None = None,
    run_id: str | None = None,
    step_id: str | None = None,
    correlation_id: CorrelationId | None = None,
    status: AgentResultStatus = AgentResultStatus.SUCCEEDED,
    output: dict[str, object] | None = None,
    metrics: dict[str, object] | None = None,
    error: ErrorEnvelope | None = None,
) -> ToolCallResult:
    return ToolCallResult(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            run_id or request.meta.run_id,
            step_id or request.meta.step_id,
            None,
            correlation_id or request.meta.correlation_id,
            NOW,
            request.meta.actor,
            status,
        ),
        tool_id=tool_id or request.tool_id,
        output={"rendered": True} if output is None else output,
        metrics={} if metrics is None else metrics,
        error=error,
    )


def _error(step_id: str = "step-router") -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code="tool.failed",
        category=ErrorCategory.TOOL,
        source=ErrorSource.TOOL,
        retryable=False,
        severity=ErrorSeverity.ERROR,
        message="tool execution failed",
        step_id=step_id,
        attempt=1,
        effect_state=EffectState.NONE,
    )


def _filesystem(
    *,
    input_resolution: ResolvedSandboxPath | None = None,
    output_pre: ResolvedSandboxPath | None = None,
    output_post: ResolvedSandboxPath | None = None,
    output_path: SandboxRelativePath = OUTPUT,
) -> RecordingSandboxFilesystem:
    return RecordingSandboxFilesystem(
        {
            INPUT.value: (
                input_resolution
                or _resolved(INPUT, exists=True, mime_type="text/plain"),
            ),
            output_path.value: (
                output_pre
                or _resolved(output_path, exists=False, mime_type=None),
                output_post
                or _resolved(output_path, exists=True, mime_type="application/pdf", size_bytes=100),
            ),
        }
    )


def _router(
    request: ToolCallRequest,
    *,
    result: ToolCallResult | None = None,
    outcome: object | None = None,
    filesystem: RecordingSandboxFilesystem | None = None,
    bind: bool = True,
    tool_call_policy: ToolCallPolicy | None = None,
    sandbox_policy: SandboxPolicy | None = None,
    executor_error: Exception | None = None,
) -> tuple[ToolRouter, RecordingToolExecutor, RecordingSandboxFilesystem]:
    configured_outcome = outcome or ToolExecutionOutcome(
        result or _result(request),
        (OUTPUT,),
    )
    executor = RecordingToolExecutor(configured_outcome, error=executor_error)
    bindings = ToolExecutorBindings(
        (ToolExecutorBinding(request.tool_id, executor),) if bind else ()
    )
    recording_filesystem = filesystem or _filesystem()
    return (
        ToolRouter(
            tool_call_policy or ToolCallPolicy(),
            sandbox_policy or SandboxPolicy(),
            recording_filesystem,
            bindings,
        ),
        executor,
        recording_filesystem,
    )


def _route(
    router: ToolRouter,
    request: ToolCallRequest,
    *,
    context: ToolRoutingContext | None = None,
    facts: PolicyFacts | None = None,
) -> ToolCallResult:
    return router.route(
        agent_id=AgentId.AG_01,
        request=request,
        context=context or _context(),
        evaluated_at=NOW,
        facts=facts
        or PolicyFacts(conditional_resolution=ConditionalResolution.ALLOW),
    )


def test_policy_deny_stops_before_filesystem_and_executor() -> None:
    request = _request()
    router, executor, filesystem = _router(request)

    with pytest.raises(ToolRoutingError) as raised:
        _route(router, request, facts=PolicyFacts())

    assert raised.value.code is ToolRoutingErrorCode.TOOL_NOT_ALLOWED
    assert executor.calls == []
    assert filesystem.resolve_calls == []


def test_tool_capability_mismatch_stops_before_filesystem_and_executor() -> None:
    request = _request(capability_id=CapabilityId("CAP-T03"))
    router, executor, filesystem = _router(request)

    with pytest.raises(ToolRoutingError) as raised:
        _route(router, request)

    assert raised.value.code is ToolRoutingErrorCode.TOOL_NOT_ALLOWED
    assert executor.calls == []
    assert filesystem.resolve_calls == []


def test_missing_binding_fails_after_sandbox_without_executor_call() -> None:
    request = _request()
    router, executor, filesystem = _router(request, bind=False)

    with pytest.raises(ToolRoutingError) as raised:
        _route(router, request)

    assert raised.value.code is ToolRoutingErrorCode.TOOL_NOT_BOUND
    assert executor.calls == []
    assert len(filesystem.resolve_calls) == 2


def test_unknown_sandbox_profile_stops_before_resolution() -> None:
    request = _request()
    sandbox_policy = SandboxPolicy(SandboxProfileRegistry(()))
    router, executor, filesystem = _router(request, sandbox_policy=sandbox_policy)

    with pytest.raises(ToolRoutingError) as raised:
        _route(router, request)

    assert raised.value.code is ToolRoutingErrorCode.TOOL_NOT_ALLOWED
    assert executor.calls == []
    assert filesystem.resolve_calls == []


@pytest.mark.parametrize("boundary", ["input", "output"])
def test_sandbox_preflight_deny_never_calls_executor(boundary: str) -> None:
    request = _request()
    filesystem = (
        _filesystem(
            input_resolution=_resolved(
                INPUT,
                exists=True,
                mime_type="text/plain",
                is_symlink=True,
            )
        )
        if boundary == "input"
        else _filesystem(
            output_pre=_resolved(
                OUTPUT,
                exists=False,
                mime_type=None,
                is_within_root=False,
            )
        )
    )
    router, executor, _ = _router(request, filesystem=filesystem)

    with pytest.raises(ToolRoutingError) as raised:
        _route(router, request)

    assert raised.value.code is ToolRoutingErrorCode.SANDBOX_DENIED
    assert executor.calls == []


@pytest.mark.parametrize(
    "input_resolution",
    [
        _resolved(
            SandboxRelativePath("input/other.txt"),
            exists=True,
            mime_type="text/plain",
        ),
        _resolved(
            INPUT,
            root_ref=SandboxRootRef(run_id="run-router", root_id="other-root"),
            exists=True,
            mime_type="text/plain",
        ),
    ],
)
def test_input_path_or_root_mismatch_never_calls_executor(
    input_resolution: ResolvedSandboxPath,
) -> None:
    request = _request()
    filesystem = _filesystem(input_resolution=input_resolution)
    router, executor, _ = _router(request, filesystem=filesystem)

    with pytest.raises(ToolRoutingError) as raised:
        _route(router, request)

    assert raised.value.code is ToolRoutingErrorCode.SANDBOX_DENIED
    assert executor.calls == []


def test_sandbox_resolution_failure_is_safe_and_never_calls_executor() -> None:
    request = _request()
    filesystem = RecordingSandboxFilesystem({})
    router, executor, _ = _router(request, filesystem=filesystem)

    with pytest.raises(ToolRoutingError) as raised:
        _route(router, request)

    assert raised.value.code is ToolRoutingErrorCode.SANDBOX_RESOLUTION_FAILED
    assert executor.calls == []
    assert "missing fake" not in str(raised.value)


def test_external_mutation_descriptor_never_reaches_sandbox_or_executor() -> None:
    request = _request()
    descriptor = replace(
        BASELINE_TOOL_REGISTRY.get(request.tool_id),
        effect_class=ToolEffectClass.EXTERNAL_MUTATION,
    )
    custom_registry = ToolRegistry((descriptor,))
    tool_policy = ToolCallPolicy(
        capability_policy=CapabilityAuthorizationPolicy(),
        tool_registry=custom_registry,
    )
    router, executor, filesystem = _router(
        request,
        tool_call_policy=tool_policy,
    )

    with pytest.raises(ToolRoutingError) as raised:
        _route(router, request)

    assert raised.value.code is ToolRoutingErrorCode.TOOL_NOT_ALLOWED
    assert executor.calls == []
    assert filesystem.resolve_calls == []


def test_forged_routing_context_is_rejected_before_resolution() -> None:
    request = _request()
    router, executor, filesystem = _router(request)
    forged = object.__new__(ToolRoutingContext)
    object.__setattr__(forged, "root_ref", ROOT)
    object.__setattr__(forged, "input_paths", [INPUT])
    object.__setattr__(forged, "output_targets", _context().output_targets)

    with pytest.raises(ToolRoutingError) as raised:
        _route(router, request, context=forged)

    assert raised.value.code is ToolRoutingErrorCode.INVALID_EXECUTION_OUTCOME
    assert executor.calls == []
    assert filesystem.resolve_calls == []


@pytest.mark.parametrize(
    ("result_changes", "code"),
    [
        ({"tool_id": "tool.convert_format"}, ToolRoutingErrorCode.RESULT_TOOL_MISMATCH),
        ({"run_id": "other-run"}, ToolRoutingErrorCode.RESULT_RUN_MISMATCH),
        ({"step_id": "other-step"}, ToolRoutingErrorCode.RESULT_STEP_MISMATCH),
        (
            {"correlation_id": CorrelationId("other-correlation")},
            ToolRoutingErrorCode.RESULT_CORRELATION_MISMATCH,
        ),
    ],
)
def test_result_identity_mismatch_is_rejected_after_one_call(
    result_changes: dict[str, object],
    code: ToolRoutingErrorCode,
) -> None:
    request = _request()
    result = _result(request, **result_changes)  # type: ignore[arg-type]
    router, executor, _ = _router(request, result=result)

    with pytest.raises(ToolRoutingError) as raised:
        _route(router, request)

    assert raised.value.code is code
    assert len(executor.calls) == 1


def test_extra_or_missing_success_output_path_is_rejected_without_retry() -> None:
    request = _request()
    extra = SandboxRelativePath("output/extra.pdf")
    outcomes = (
        ToolExecutionOutcome(_result(request), (OUTPUT, extra)),
        ToolExecutionOutcome(_result(request), ()),
    )

    for outcome in outcomes:
        router, executor, _ = _router(request, outcome=outcome)
        with pytest.raises(ToolRoutingError) as raised:
            _route(router, request)
        assert raised.value.code is ToolRoutingErrorCode.OUTPUT_PATH_MISMATCH
        assert len(executor.calls) == 1


def test_malformed_outcome_and_executor_failure_are_closed_without_retry() -> None:
    request = _request()
    malformed_router, malformed_executor, _ = _router(request, outcome=object())
    failed_router, failed_executor, _ = _router(
        request,
        executor_error=RuntimeError("sensitive provider detail"),
    )

    with pytest.raises(ToolRoutingError) as malformed:
        _route(malformed_router, request)
    with pytest.raises(ToolRoutingError) as failed:
        _route(failed_router, request)

    assert malformed.value.code is ToolRoutingErrorCode.INVALID_EXECUTION_OUTCOME
    assert failed.value.code is ToolRoutingErrorCode.EXECUTOR_FAILED
    assert "sensitive" not in str(failed.value)
    assert len(malformed_executor.calls) == 1
    assert len(failed_executor.calls) == 1


@pytest.mark.parametrize(
    ("field_name", "payload"),
    [
        ("output", {"providerConfig": {"endpoint": "redacted"}}),
        ("metrics", {"sandbox_root": "forged"}),
    ],
)
def test_result_authority_smuggling_is_rejected(
    field_name: str,
    payload: dict[str, object],
) -> None:
    request = _request()
    result = _result(request, **{field_name: payload})
    router, executor, _ = _router(request, result=result)

    with pytest.raises(ToolRoutingError) as raised:
        _route(router, request)

    assert raised.value.code is ToolRoutingErrorCode.INVALID_EXECUTION_OUTCOME
    assert len(executor.calls) == 1


def test_success_cannot_mask_error_and_failed_result_remains_failed() -> None:
    request = _request()
    masked = _result(request, error=_error())
    masked_router, masked_executor, _ = _router(request, result=masked)
    with pytest.raises(ToolRoutingError) as raised:
        _route(masked_router, request)
    assert raised.value.code is ToolRoutingErrorCode.INVALID_EXECUTION_OUTCOME
    assert len(masked_executor.calls) == 1

    failed_result = _result(
        request,
        status=AgentResultStatus.FAILED,
        output={},
        error=_error(),
    )
    failed_outcome = ToolExecutionOutcome(failed_result, ())
    failed_filesystem = RecordingSandboxFilesystem(
        {
            INPUT.value: (_resolved(INPUT, exists=True, mime_type="text/plain"),),
            OUTPUT.value: (_resolved(OUTPUT, exists=False, mime_type=None),),
        }
    )
    failed_router, failed_executor, _ = _router(
        request,
        outcome=failed_outcome,
        filesystem=failed_filesystem,
    )

    accepted = _route(failed_router, request)

    assert accepted.meta.status is AgentResultStatus.FAILED
    assert accepted.error is failed_result.error
    assert len(failed_executor.calls) == 1


def test_forged_failed_result_without_error_is_rejected_after_one_call() -> None:
    request = _request()
    failed_meta = ContractMeta(
        AGENT_CONTRACT_SCHEMA_V1_0,
        request.meta.run_id,
        request.meta.step_id,
        None,
        request.meta.correlation_id,
        NOW,
        request.meta.actor,
        AgentResultStatus.FAILED,
    )
    forged = object.__new__(ToolCallResult)
    object.__setattr__(forged, "meta", failed_meta)
    object.__setattr__(forged, "tool_id", request.tool_id)
    object.__setattr__(forged, "output", None)
    object.__setattr__(forged, "artifacts", ())
    object.__setattr__(forged, "metrics", {})
    object.__setattr__(forged, "error", None)
    router, executor, _ = _router(
        request,
        outcome=ToolExecutionOutcome(forged, ()),
    )

    with pytest.raises(ToolRoutingError) as raised:
        _route(router, request)

    assert raised.value.code is ToolRoutingErrorCode.INVALID_EXECUTION_OUTCOME
    assert len(executor.calls) == 1
