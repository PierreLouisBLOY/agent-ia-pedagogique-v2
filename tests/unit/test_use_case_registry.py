from dataclasses import FrozenInstanceError

import pytest

from backend.agent_runtime.application_routing import (
    BASELINE_USE_CASE_REGISTRY,
    UnknownUseCaseError,
    UseCaseDescriptor,
    UseCaseRegistry,
)
from backend.agent_runtime.registry import BASELINE_CAPABILITY_REGISTRY
from backend.core_contracts.capability import CapabilityId


def _descriptor(
    use_case_id: str = "application.custom",
    canonical_name: str = "custom",
    capability_id: str = "CAP-R01",
) -> UseCaseDescriptor:
    return UseCaseDescriptor(
        use_case_id,
        canonical_name,
        CapabilityId(capability_id),
        "C-12",
        "C-13",
        False,
    )


def test_baseline_contains_exact_six_application_routes() -> None:
    assert {
        descriptor.use_case_id: descriptor.capability_id.value
        for descriptor in BASELINE_USE_CASE_REGISTRY.all()
    } == {
        "application.read_canonical_resource": "CAP-R01",
        "application.read_production": "CAP-R02",
        "application.read_metadata_status": "CAP-R03",
        "application.run_deterministic_validation": "CAP-A01",
        "application.request_promotion": "CAP-A02",
        "application.export_artifact": "CAP-A03",
    }
    assert BASELINE_USE_CASE_REGISTRY.get(
        "application.request_promotion"
    ).idempotency_required
    assert BASELINE_USE_CASE_REGISTRY.get(
        "application.export_artifact"
    ).idempotency_required


def test_registry_is_exact_match_and_filters_by_capability() -> None:
    descriptor = BASELINE_USE_CASE_REGISTRY.get("application.read_production")

    assert BASELINE_USE_CASE_REGISTRY.contains(descriptor.use_case_id)
    assert BASELINE_USE_CASE_REGISTRY.by_capability(CapabilityId("CAP-R02")) == (
        descriptor,
    )
    with pytest.raises(UnknownUseCaseError):
        BASELINE_USE_CASE_REGISTRY.get("read_production")


@pytest.mark.parametrize("duplicate_field", ["use_case_id", "canonical_name"])
def test_registry_rejects_duplicate_identity(duplicate_field: str) -> None:
    first = _descriptor()
    second = _descriptor(
        use_case_id=(first.use_case_id if duplicate_field == "use_case_id" else "application.two"),
        canonical_name=(first.canonical_name if duplicate_field == "canonical_name" else "two"),
        capability_id="CAP-R02",
    )

    with pytest.raises(ValueError):
        UseCaseRegistry((first, second))


@pytest.mark.parametrize("capability_id", ["CAP-UNKNOWN", "CAP-G01", "CAP-T01", "CAP-O01"])
def test_registry_rejects_unknown_or_non_application_capability(
    capability_id: str,
) -> None:
    with pytest.raises(ValueError):
        UseCaseRegistry((_descriptor(capability_id=capability_id),))


def test_descriptor_and_registry_are_immutable_and_handler_free() -> None:
    descriptor = _descriptor()
    registry = UseCaseRegistry((descriptor,), BASELINE_CAPABILITY_REGISTRY)

    with pytest.raises(FrozenInstanceError):
        descriptor.canonical_name = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        registry._descriptors = ()  # type: ignore[misc]
    assert not any(
        hasattr(descriptor, field)
        for field in ("handler", "callable", "handler_path", "import_path", "provider")
    )
