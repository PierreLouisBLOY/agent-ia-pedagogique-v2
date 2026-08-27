from __future__ import annotations

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
from backend.agent_runtime.sandbox import (
    ResolvedSandboxPath,
    SandboxOperation,
    SandboxPolicy,
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

NOW = Instant(datetime(2026, 8, 26, 16, 0, tzinfo=UTC))
BEFORE = Instant(NOW.value - timedelta(hours=1))
AFTER = Instant(NOW.value + timedelta(hours=1))
ROOT = SandboxRootRef(run_id="run-pipeline", root_id="root-pipeline")
INPUT = SandboxRelativePath("input/source.txt")
OUTPUT = SandboxRelativePath("output/result.pdf")


def _request(tool_id: str, capability_code: str, timeout: int | None) -> ToolCallRequest:
    capability_id = CapabilityId(capability_code)
    actor = ActorRef(ActorKind.AGENT, AgentId.AG_01.value)
    return ToolCallRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-pipeline",
            "step-pipeline",
            None,
            CorrelationId("corr-pipeline"),
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
        timeout=timeout,
        idempotency_key=f"idem-{tool_id}",
    )


def _result(request: ToolCallRequest) -> ToolCallResult:
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
        output={"artifact_created": True},
        artifacts=("artifact-output",),
        metrics={"duration_ms": 10},
    )


def _resolved(
    path: SandboxRelativePath,
    *,
    exists: bool,
    mime_type: str | None,
    root_ref: SandboxRootRef = ROOT,
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
        "size_bytes": (100 if exists else 0) if size_bytes is None else size_bytes,
        "observed_extension": path.extension,
        "observed_mime_type": mime_type,
        "has_active_content": False,
        "is_executable_content": False,
    }
    values.update(overrides)
    return ResolvedSandboxPath(**values)  # type: ignore[arg-type]


def _context() -> ToolRoutingContext:
    return ToolRoutingContext(
        root_ref=ROOT,
        input_paths=(INPUT,),
        output_targets=(
            SandboxOutputTarget(
                OUTPUT,
                SandboxOperation.CREATE,
                100,
                "application/pdf",
            ),
        ),
    )


def _pipeline(
    request: ToolCallRequest,
    *,
    post_output: ResolvedSandboxPath | None = None,
) -> tuple[ToolRouter, RecordingToolExecutor, RecordingSandboxFilesystem]:
    outcome = ToolExecutionOutcome(_result(request), (OUTPUT,))
    executor = RecordingToolExecutor(outcome)
    filesystem = RecordingSandboxFilesystem(
        {
            INPUT.value: (
                _resolved(INPUT, exists=True, mime_type="text/plain"),
            ),
            OUTPUT.value: (
                _resolved(OUTPUT, exists=False, mime_type=None),
                post_output
                or _resolved(OUTPUT, exists=True, mime_type="application/pdf"),
            ),
        }
    )
    router = ToolRouter(
        ToolCallPolicy(),
        SandboxPolicy(),
        filesystem,
        ToolExecutorBindings((ToolExecutorBinding(request.tool_id, executor),)),
    )
    return router, executor, filesystem


def _route(router: ToolRouter, request: ToolCallRequest) -> ToolCallResult:
    return router.route(
        agent_id=AgentId.AG_01,
        request=request,
        context=_context(),
        evaluated_at=NOW,
        facts=PolicyFacts(conditional_resolution=ConditionalResolution.ALLOW),
    )


@pytest.mark.parametrize(
    ("tool_id", "capability_code", "requested_timeout", "expected_timeout"),
    [
        ("tool.render_document", "CAP-T02", None, 120),
        ("tool.convert_format", "CAP-T03", 30, 30),
    ],
)
def test_t02_t03_follow_the_complete_authorized_sandbox_pipeline(
    tool_id: str,
    capability_code: str,
    requested_timeout: int | None,
    expected_timeout: int,
) -> None:
    request = _request(tool_id, capability_code, requested_timeout)
    router, executor, filesystem = _pipeline(request)

    accepted = _route(router, request)

    expected = _result(request)
    assert accepted.meta == expected.meta
    assert accepted.tool_id == expected.tool_id
    assert accepted.output == expected.output
    assert accepted.artifacts == expected.artifacts
    assert accepted.content_label is not None
    assert accepted.security_assessment is not None
    assert len(executor.calls) == 1
    prepared = executor.calls[0]
    assert prepared.request is request
    assert prepared.descriptor.tool_id == tool_id
    assert prepared.tool_decision.tool_id == tool_id
    assert prepared.effective_timeout == expected_timeout
    assert prepared.idempotency_key == request.idempotency_key
    assert prepared.input_contract_id == prepared.descriptor.input_contract_id
    assert prepared.output_contract_id == prepared.descriptor.output_contract_id
    assert prepared.argument_security_assessment is not None
    assert [path.value for _, path in filesystem.resolve_calls] == [
        INPUT.value,
        OUTPUT.value,
        OUTPUT.value,
    ]
    assert len(filesystem.inspect_calls) == 3


@pytest.mark.parametrize(
    "post_output",
    [
        _resolved(
            OUTPUT,
            exists=True,
            mime_type="application/pdf",
            is_symlink=True,
        ),
        _resolved(
            OUTPUT,
            exists=True,
            mime_type="application/pdf",
            is_within_root=False,
        ),
        _resolved(OUTPUT, exists=True, mime_type="image/png"),
        _resolved(
            OUTPUT,
            exists=True,
            mime_type="application/pdf",
            size_bytes=50 * 1024 * 1024 + 1,
        ),
        _resolved(
            OUTPUT,
            exists=True,
            mime_type="application/pdf",
            has_active_content=True,
        ),
        _resolved(
            OUTPUT,
            exists=True,
            mime_type="application/pdf",
            is_executable_content=True,
        ),
    ],
)
def test_post_execution_output_is_reinspected_and_denied_fail_closed(
    post_output: ResolvedSandboxPath,
) -> None:
    request = _request("tool.render_document", "CAP-T02", 60)
    router, executor, filesystem = _pipeline(request, post_output=post_output)

    with pytest.raises(ToolRoutingError) as raised:
        _route(router, request)

    assert raised.value.code is ToolRoutingErrorCode.OUTPUT_SANDBOX_DENIED
    assert len(executor.calls) == 1
    assert len(filesystem.resolve_calls) == 3
    assert len(filesystem.inspect_calls) == 3


def test_post_execution_root_and_path_mismatch_are_denied() -> None:
    request = _request("tool.convert_format", "CAP-T03", 60)
    other_root = SandboxRootRef(run_id="run-pipeline", root_id="other-root")
    other_path = SandboxRelativePath("output/other.pdf")
    invalid_outputs = (
        _resolved(
            OUTPUT,
            exists=True,
            mime_type="application/pdf",
            root_ref=other_root,
        ),
        _resolved(other_path, exists=True, mime_type="application/pdf"),
    )

    for post_output in invalid_outputs:
        router, executor, _ = _pipeline(request, post_output=post_output)
        with pytest.raises(ToolRoutingError) as raised:
            _route(router, request)
        assert raised.value.code is ToolRoutingErrorCode.OUTPUT_SANDBOX_DENIED
        assert len(executor.calls) == 1
