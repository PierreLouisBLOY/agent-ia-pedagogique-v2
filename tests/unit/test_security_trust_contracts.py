from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from backend.agent_runtime.contracts import (
    ContentOrigin,
    ContentRole,
    ContentTrustClass,
    ContentTrustLabel,
    SecurityBoundary,
)


def test_security_boundary_vocabulary_is_closed_and_provider_neutral() -> None:
    assert {item.name for item in SecurityBoundary} == {
        "USER_INPUT",
        "DOCUMENT",
        "EVIDENCE",
        "AGENT",
        "TOOL",
        "APPLICATION",
        "GATE",
        "RUNTIME",
        "RECOVERY",
        "INFRASTRUCTURE",
    }
    assert all("provider" not in item.value for item in SecurityBoundary)


def test_content_origin_and_role_vocabularies_are_closed() -> None:
    assert {item.name for item in ContentOrigin} == {
        "USER_INPUT",
        "DOCUMENT",
        "EVIDENCE",
        "AGENT_OUTPUT",
        "TOOL_OUTPUT",
        "APPLICATION_OUTPUT",
        "REVIEW_OUTPUT",
        "CORRECTION_OUTPUT",
        "RUNTIME_DATA",
        "RECOVERY_DATA",
        "INTERNAL_CONTROL",
    }
    assert {item.name for item in ContentRole} == {
        "INSTRUCTION",
        "DATA",
        "EVIDENCE",
        "RESULT",
        "METADATA",
        "DIAGNOSTIC",
    }


def test_trust_class_is_conservative_and_has_no_authority_vocabulary() -> None:
    assert set(ContentTrustClass) == {
        ContentTrustClass.UNTRUSTED,
        ContentTrustClass.STRUCTURALLY_VALIDATED,
    }
    values = {item.value.upper() for item in ContentTrustClass}
    assert values.isdisjoint(
        {"ALLOW", "REQUEST", "DELEGATE", "APPROVED", "PROMOTE", "TRUSTED_INTERNAL"}
    )
    with pytest.raises(ValueError):
        ContentTrustClass("trusted_internal")


def test_content_trust_label_is_immutable_minimal_provenance() -> None:
    label = ContentTrustLabel(
        origin=ContentOrigin.DOCUMENT,
        role=ContentRole.DATA,
        trust_class=ContentTrustClass.STRUCTURALLY_VALIDATED,
        source_ref="document:lesson-1",
    )

    assert {item.name for item in fields(ContentTrustLabel)} == {
        "origin",
        "role",
        "trust_class",
        "source_ref",
    }
    assert label.source_ref == "document:lesson-1"
    assert not hasattr(label, "__dict__")
    with pytest.raises(FrozenInstanceError):
        label.role = ContentRole.INSTRUCTION  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("origin", "document", "origin must be"),
        ("role", "data", "role must be"),
        ("trust_class", "untrusted", "trust_class must be"),
    ],
)
def test_content_trust_label_rejects_untyped_vocabulary(
    field_name: str,
    value: object,
    message: str,
) -> None:
    values: dict[str, object] = {
        "origin": ContentOrigin.AGENT_OUTPUT,
        "role": ContentRole.RESULT,
        "trust_class": ContentTrustClass.UNTRUSTED,
    }
    values[field_name] = value

    with pytest.raises(TypeError, match=message):
        ContentTrustLabel(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "origin",
    [
        ContentOrigin.AGENT_OUTPUT,
        ContentOrigin.TOOL_OUTPUT,
        ContentOrigin.APPLICATION_OUTPUT,
        ContentOrigin.REVIEW_OUTPUT,
        ContentOrigin.CORRECTION_OUTPUT,
    ],
)
def test_generated_outputs_never_gain_authority_from_a_trust_label(
    origin: ContentOrigin,
) -> None:
    label = ContentTrustLabel(
        origin=origin,
        role=ContentRole.RESULT,
        trust_class=ContentTrustClass.STRUCTURALLY_VALIDATED,
    )

    assert label.trust_class is ContentTrustClass.STRUCTURALLY_VALIDATED
    assert all(
        authority_field not in {item.name for item in fields(label)}
        for authority_field in ("authority", "decision", "permission", "approved")
    )


def test_content_trust_label_rejects_invalid_source_reference() -> None:
    with pytest.raises(ValueError, match="source_ref must not be empty"):
        ContentTrustLabel(
            origin=ContentOrigin.EVIDENCE,
            role=ContentRole.EVIDENCE,
            trust_class=ContentTrustClass.UNTRUSTED,
            source_ref=" ",
        )
