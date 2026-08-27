from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, replace
from types import MappingProxyType
from typing import get_origin, get_type_hints

import pytest

from backend.agent_runtime.contracts import (
    AgentId,
    AgentInvocation,
    AgentResult,
    DelegationEnvelope,
    DelegationResult,
    InvocationStatus,
    SamplingDecision,
    SpanId,
    ToolCallRequest,
    TraceContext,
    TraceId,
    UseCaseRequest,
    ValidatedAgentHandoff,
)
from backend.agent_runtime.observability import TraceContextPolicy
from tests.support.multi_agent_security_fixtures import (
    delegation,
    meta,
)


def test_contract_meta_trace_flags_remain_opaque_even_with_trace_like_keys() -> None:
    legacy = {
        "trace_id": "legacy-trace",
        "span_id": "legacy-span",
        "sampled": True,
    }
    contract_meta = replace(
        meta(InvocationStatus.PLANNED, AgentId.AG_01),
        trace_flags=legacy,
    )

    assert isinstance(contract_meta.trace_flags, MappingProxyType)
    assert dict(contract_meta.trace_flags) == legacy
    assert not hasattr(contract_meta, "trace_context")
    assert not isinstance(contract_meta.trace_flags, TraceContext)


def test_delegation_trace_context_remains_explicitly_legacy_and_opaque() -> None:
    legacy = {
        "trace_id": "legacy-delegation-trace",
        "span_id": "legacy-delegation-span",
        "sampled": True,
    }
    delegated = replace(delegation(), trace_context=legacy)
    annotation = get_type_hints(DelegationEnvelope)["trace_context"]

    assert get_origin(annotation) is Mapping
    assert isinstance(delegated.trace_context, MappingProxyType)
    assert dict(delegated.trace_context) == legacy
    assert not isinstance(delegated.trace_context, TraceContext)
    assert "observability_trace_context" not in {
        item.name for item in fields(DelegationEnvelope)
    }


def test_legacy_delegation_mapping_is_never_accepted_as_typed_parent() -> None:
    delegated = replace(
        delegation(),
        trace_context={"trace_id": "legacy", "sampled": True},
    )

    with pytest.raises(TypeError, match="parent must be a TraceContext"):
        TraceContextPolicy().child(  # type: ignore[arg-type]
            parent=delegated.trace_context,
            child_span_id=SpanId("span-agent-invocation-01"),
        )


def test_agent_child_context_is_a_separate_typed_sidecar() -> None:
    policy = TraceContextPolicy()
    parent = policy.root(
        trace_id=TraceId("trace-run-01"),
        span_id=SpanId("span-orchestrator-01"),
        sampling_decision=SamplingDecision.RECORD_ONLY,
    )
    child_sidecar = policy.child(
        parent=parent,
        child_span_id=SpanId("span-agent-invocation-01"),
    )
    delegated = delegation()

    assert isinstance(child_sidecar, TraceContext)
    assert delegated.trace_context == {}
    assert not hasattr(delegated, "typed_trace_context")


def test_invocation_result_and_security_handoff_do_not_own_trace_context() -> None:
    for contract in (
        AgentInvocation,
        AgentResult,
        DelegationResult,
        ValidatedAgentHandoff,
    ):
        assert "trace_context" not in {item.name for item in fields(contract)}


def test_tool_and_application_requests_have_no_trace_payload_field() -> None:
    assert "trace_context" not in {item.name for item in fields(ToolCallRequest)}
    assert "trace_context" not in {item.name for item in fields(UseCaseRequest)}
