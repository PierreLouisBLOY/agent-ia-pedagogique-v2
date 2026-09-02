from __future__ import annotations

from backend.adapters.inbound.application import ResourceLibraryUseCaseInbound
from backend.agent_runtime.application_routing import (
    BASELINE_USE_CASE_REGISTRY,
    UseCaseInboundBinding,
    UseCaseInboundBindings,
    UseCaseRouter,
)
from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.policy import CapabilityAuthorizationPolicy
from backend.modules.resource_library.application.queries import GetResourceQuery
from backend.modules.resource_library.domain.value_objects.persistence_vocabulary import (
    ResourceIdentityStatus,
    ResourceType,
)
from backend.modules.resource_library.ports.outbound import ResourceRecord
from tests.support.use_case_routing_fakes import NOW, make_request


class FixedResourceStore:
    def load_resource(self, resource_ref: str) -> ResourceRecord | None:
        return ResourceRecord(
            resource_ref,
            ResourceType.COURSE,
            "Management",
            ResourceIdentityStatus.ACTIVE,
        )


def test_cap_r01_routes_once_to_the_real_m03_get_resource_inbound() -> None:
    request, context = make_request(payload={"resource_ref": "resource:1"})
    inbound = ResourceLibraryUseCaseInbound(GetResourceQuery(FixedResourceStore()))
    router = UseCaseRouter(
        CapabilityAuthorizationPolicy(),
        BASELINE_USE_CASE_REGISTRY,
        UseCaseInboundBindings(
            (UseCaseInboundBinding(request.use_case_id, inbound),)
        ),
    )

    result = router.route(
        agent_id=AgentId.AG_01,
        request=request,
        context=context,
        evaluated_at=NOW,
    )

    assert result.outcome.success is True
    assert result.outcome.data == {
        "resource_ref": "resource:1",
        "resource_type": "COURSE",
        "canonical_title": "Management",
        "identity_status": "ACTIVE",
    }
