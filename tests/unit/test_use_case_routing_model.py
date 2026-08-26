from dataclasses import FrozenInstanceError

import pytest

from backend.agent_runtime.application_routing import (
    UseCaseInboundBinding,
    UseCaseInboundBindings,
    UseCaseRoutingContext,
)
from tests.support.use_case_routing_fakes import (
    RecordingApplicationInbound,
    make_request,
    make_result,
)


def test_routing_context_and_bindings_are_immutable_exact_match_values() -> None:
    request, context = make_request()
    inbound = RecordingApplicationInbound(make_result(request))
    binding = UseCaseInboundBinding(request.use_case_id, inbound)
    bindings = UseCaseInboundBindings((binding,))

    assert bindings.get(request.use_case_id) is inbound
    assert bindings.all() == (binding,)
    with pytest.raises(FrozenInstanceError):
        context.permission_scope_ref = "changed"  # type: ignore[misc]
    with pytest.raises(LookupError):
        bindings.get("application.unknown")


def test_bindings_reject_duplicates_and_non_ports() -> None:
    request, _ = make_request()
    inbound = RecordingApplicationInbound(make_result(request))
    binding = UseCaseInboundBinding(request.use_case_id, inbound)

    with pytest.raises(ValueError):
        UseCaseInboundBindings((binding, binding))
    with pytest.raises(TypeError):
        UseCaseInboundBinding(request.use_case_id, object())  # type: ignore[arg-type]


def test_context_requires_canonical_types() -> None:
    _, context = make_request()

    with pytest.raises(TypeError):
        UseCaseRoutingContext(
            step=context.step,
            permission_scope_ref="scope",
            permission_scope=object(),  # type: ignore[arg-type]
        )
