from __future__ import annotations

from dataclasses import dataclass, field

from backend.core_contracts.outcome import OutcomeStatus
from backend.modules.resource_library.application.dto.input import GetResourceRequest
from backend.modules.resource_library.application.queries import GetResourceQuery
from backend.modules.resource_library.domain.value_objects.persistence_vocabulary import (
    ResourceIdentityStatus,
    ResourceType,
)
from backend.modules.resource_library.ports.outbound import ResourceRecord
from backend.shared_kernel.correlation import CorrelationId


@dataclass
class RecordingResourceStore:
    record: ResourceRecord | None
    calls: list[str] = field(default_factory=list)

    def load_resource(self, resource_ref: str) -> ResourceRecord | None:
        self.calls.append(resource_ref)
        return self.record


def test_get_resource_maps_one_op03_record_to_a_typed_resource_view() -> None:
    record = ResourceRecord(
        "resource:1",
        ResourceType.EXERCISE_SET,
        "Fonctions du management",
        ResourceIdentityStatus.ACTIVE,
    )
    store = RecordingResourceStore(record)

    result = GetResourceQuery(store).get_resource(
        request=GetResourceRequest("resource:1"),
        correlation_id=CorrelationId("corr-resource"),
    )

    assert result.outcome_status is OutcomeStatus.SUCCESS
    assert result.success is True
    assert result.data is not None
    assert result.data.resource_ref == "resource:1"
    assert result.data.canonical_title == "Fonctions du management"
    assert store.calls == ["resource:1"]


def test_get_resource_returns_the_closed_canonical_missing_resource_error() -> None:
    store = RecordingResourceStore(None)

    result = GetResourceQuery(store).get_resource(
        request=GetResourceRequest("resource:missing"),
        correlation_id=CorrelationId("corr-missing"),
    )

    assert result.outcome_status is OutcomeStatus.REJECTED
    assert result.success is False
    assert result.data is None
    assert len(result.business_errors) == 1
    error = result.business_errors[0]
    assert error.code.value == "RES_NOT_FOUND"
    assert error.retryable is False
    assert error.blocking is True
    assert store.calls == ["resource:missing"]
