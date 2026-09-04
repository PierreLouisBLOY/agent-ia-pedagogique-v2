from __future__ import annotations

from typing import cast

import pytest

from backend.modules.resource_library.domain.value_objects import (
    ResourceAvailabilityStatus,
    ResourceCanonicalityStatus,
    ResourceSemanticState,
)


def test_availability_and_canonicality_are_independent_dimensions() -> None:
    active_with_unknown_canonicality = ResourceSemanticState(
        ResourceAvailabilityStatus.ACTIVE,
        ResourceCanonicalityStatus.UNKNOWN,
    )
    canonical_with_unknown_availability = ResourceSemanticState(
        ResourceAvailabilityStatus.UNKNOWN,
        ResourceCanonicalityStatus.CANONICAL,
    )
    assert active_with_unknown_canonicality.canonicality_status.value == "UNKNOWN"
    assert canonical_with_unknown_availability.availability_status.value == "UNKNOWN"


def test_no_unproven_cross_dimension_combination_is_authorized() -> None:
    with pytest.raises(ValueError, match="combined .* are not authorized"):
        ResourceSemanticState(
            ResourceAvailabilityStatus.ACTIVE,
            ResourceCanonicalityStatus.CANONICAL,
        )


def test_unknown_is_not_encoded_as_false() -> None:
    assert set(ResourceAvailabilityStatus) == {
        ResourceAvailabilityStatus.UNKNOWN,
        ResourceAvailabilityStatus.ACTIVE,
    }
    assert set(ResourceCanonicalityStatus) == {
        ResourceCanonicalityStatus.UNKNOWN,
        ResourceCanonicalityStatus.CANONICAL,
    }
    assert "NON_CANONICAL" not in {value.value for value in ResourceCanonicalityStatus}


@pytest.mark.parametrize(
    ("availability", "canonicality", "message"),
    (
        (
            cast(ResourceAvailabilityStatus, ResourceCanonicalityStatus.CANONICAL),
            ResourceCanonicalityStatus.UNKNOWN,
            "availability_status",
        ),
        (
            ResourceAvailabilityStatus.UNKNOWN,
            cast(ResourceCanonicalityStatus, ResourceAvailabilityStatus.ACTIVE),
            "canonicality_status",
        ),
    ),
)
def test_semantic_dimensions_are_type_checked(
    availability: ResourceAvailabilityStatus,
    canonicality: ResourceCanonicalityStatus,
    message: str,
) -> None:
    with pytest.raises(TypeError, match=message):
        ResourceSemanticState(availability, canonicality)
