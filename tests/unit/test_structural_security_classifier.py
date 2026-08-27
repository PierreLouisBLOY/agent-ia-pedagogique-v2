from __future__ import annotations

import pytest

from backend.agent_runtime.security import (
    contains_structural_keys,
    normalize_structural_key,
    structural_key_locations,
)

FORBIDDEN = frozenset({"capability_id", "permission_scope", "gate_decision"})


@pytest.mark.parametrize(
    "key",
    (
        "capability_id",
        "capabilityId",
        "CapabilityID",
        "capability-id",
        "CAPABILITY ID",
        "capabilityid",
    ),
)
def test_structural_classifier_normalizes_case_and_separators(key: str) -> None:
    assert normalize_structural_key(key).replace("_", "") == "capabilityid"
    assert contains_structural_keys({key: "CAP-T03"}, forbidden_keys=FORBIDDEN)


def test_structural_classifier_finds_nested_keys_with_safe_locations() -> None:
    value = {"outer": ({"permissionScope": "admin"}, {"gate-decision": "yes"})}

    assert structural_key_locations(
        value,
        forbidden_keys=FORBIDDEN,
        root_location="tool_arguments",
    ) == (
        "tool_arguments.outer.0.permission_scope",
        "tool_arguments.outer.1.gate_decision",
    )


def test_pedagogical_text_mentioning_authority_names_is_not_a_structural_key() -> None:
    value = {
        "lesson": (
            "Explain why permission and capability_id are fields in this JSON example"
        )
    }

    assert not contains_structural_keys(value, forbidden_keys=FORBIDDEN)
