from dataclasses import FrozenInstanceError, fields

import pytest

from backend.agent_runtime.registry import (
    BASELINE_CAPABILITY_REGISTRY,
    BASELINE_TOOL_REGISTRY,
    CapabilityClass,
    CapabilityDescriptor,
    CapabilityExecutionRoute,
    CapabilityRegistry,
    CapabilityRisk,
    ToolDescriptor,
    ToolEffectClass,
    ToolRegistry,
    ToolRegistryConfigurationError,
    UnknownToolError,
)
from backend.core_contracts.capability import CapabilityId


def _descriptor(**overrides: object) -> ToolDescriptor:
    values: dict[str, object] = {
        "tool_id": "tool.render_document",
        "canonical_name": "render_document",
        "capability_id": CapabilityId("CAP-T02"),
        "input_contract_id": "tool.render_document.input.v1",
        "output_contract_id": "tool.render_document.output.v1",
        "effect_class": ToolEffectClass.LOCAL_FILE_TRANSFORM,
        "sandbox_profile_id": "sandbox.local_file_transform.v1",
        "idempotency_required": True,
        "timeout_ceiling": 120,
    }
    values.update(overrides)
    return ToolDescriptor(**values)  # type: ignore[arg-type]


def test_effect_classification_is_closed_and_distinct_from_effect_state() -> None:
    assert {item.value for item in ToolEffectClass} == {
        "READ_ONLY",
        "PURE_COMPUTE",
        "LOCAL_FILE_TRANSFORM",
        "EXTERNAL_MUTATION",
    }


def test_baseline_registry_contains_only_t02_and_t03_local_tools() -> None:
    descriptors = BASELINE_TOOL_REGISTRY.all()

    assert tuple(item.tool_id for item in descriptors) == (
        "tool.render_document",
        "tool.convert_format",
    )
    assert tuple(item.capability_id.value for item in descriptors) == (
        "CAP-T02",
        "CAP-T03",
    )
    assert all(
        item.effect_class is ToolEffectClass.LOCAL_FILE_TRANSFORM
        and item.sandbox_profile_id == "sandbox.local_file_transform.v1"
        and item.idempotency_required
        and item.timeout_ceiling == 120
        for item in descriptors
    )
    assert BASELINE_TOOL_REGISTRY.by_capability(CapabilityId("CAP-T01")) == ()
    assert BASELINE_TOOL_REGISTRY.by_capability(CapabilityId("CAP-T04")) == ()


def test_registry_lookup_is_exact_and_unknown_tool_fails_closed() -> None:
    descriptor = BASELINE_TOOL_REGISTRY.get("tool.render_document")

    assert BASELINE_TOOL_REGISTRY.contains(descriptor.tool_id)
    assert not BASELINE_TOOL_REGISTRY.contains("tool.unknown")
    with pytest.raises(UnknownToolError, match="unknown tool"):
        BASELINE_TOOL_REGISTRY.get("tool.unknown")


def test_registry_rejects_duplicate_ids_and_names() -> None:
    descriptor = _descriptor()

    with pytest.raises(ToolRegistryConfigurationError, match="duplicate tool_id"):
        ToolRegistry((descriptor, _descriptor(canonical_name="render_document_copy")))
    with pytest.raises(ToolRegistryConfigurationError, match="duplicate canonical_name"):
        ToolRegistry((descriptor, _descriptor(tool_id="tool.render_document.copy")))


def test_registry_rejects_unknown_capability() -> None:
    with pytest.raises(ToolRegistryConfigurationError, match="unknown capability"):
        ToolRegistry((_descriptor(capability_id=CapabilityId("CAP-T99")),))


def test_registry_rejects_non_technical_utility_capability() -> None:
    with pytest.raises(ToolRegistryConfigurationError, match="TECHNICAL_UTILITY"):
        ToolRegistry((_descriptor(capability_id=CapabilityId("CAP-A01")),))


def test_registry_rejects_non_utility_route() -> None:
    capability = CapabilityDescriptor(
        capability_id=CapabilityId("CAP-T99"),
        canonical_name="invalid_utility_route",
        capability_class=CapabilityClass.TECHNICAL_UTILITY,
        risk=CapabilityRisk.R0,
        execution_route=CapabilityExecutionRoute.APPLICATION,
        owner_agent=None,
    )
    capability_registry = CapabilityRegistry((capability,))

    with pytest.raises(ToolRegistryConfigurationError, match="UTILITY route"):
        ToolRegistry(
            (_descriptor(capability_id=capability.capability_id),),
            capability_registry=capability_registry,
        )


def test_local_file_transform_requires_sandbox_and_idempotency() -> None:
    with pytest.raises(ValueError, match="sandbox_profile_id"):
        _descriptor(sandbox_profile_id=None)
    with pytest.raises(ValueError, match="require idempotency"):
        _descriptor(idempotency_required=False)


@pytest.mark.parametrize(
    "effect_class", (ToolEffectClass.READ_ONLY, ToolEffectClass.PURE_COMPUTE)
)
def test_non_mutating_tools_do_not_claim_a_sandbox(
    effect_class: ToolEffectClass,
) -> None:
    with pytest.raises(ValueError, match="must not declare a sandbox"):
        _descriptor(effect_class=effect_class, idempotency_required=False)


def test_external_mutation_requires_idempotency() -> None:
    with pytest.raises(ValueError, match="require idempotency"):
        _descriptor(
            effect_class=ToolEffectClass.EXTERNAL_MUTATION,
            sandbox_profile_id=None,
            idempotency_required=False,
        )


def test_descriptor_rejects_negative_or_boolean_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_ceiling must be >= 0"):
        _descriptor(timeout_ceiling=-1)
    with pytest.raises(TypeError, match="timeout_ceiling must be a number"):
        _descriptor(timeout_ceiling=True)
    with pytest.raises(ValueError, match="timeout_ceiling must be finite"):
        _descriptor(timeout_ceiling=float("nan"))
    with pytest.raises(ValueError, match="timeout_ceiling must be finite"):
        _descriptor(timeout_ceiling=float("inf"))


def test_descriptors_and_registry_are_immutable_and_store_no_handler_or_risk() -> None:
    descriptor = BASELINE_TOOL_REGISTRY.get("tool.render_document")
    field_names = {item.name for item in fields(ToolDescriptor)}

    assert field_names.isdisjoint(
        {"handler", "callable", "provider", "credential", "risk"}
    )
    assert all(not callable(getattr(descriptor, name)) for name in field_names)
    with pytest.raises(FrozenInstanceError):
        descriptor.tool_id = "tool.changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        BASELINE_TOOL_REGISTRY._by_id["tool.changed"] = descriptor  # type: ignore[index]


def test_registry_uses_the_canonical_capability_registry() -> None:
    assert BASELINE_TOOL_REGISTRY.capability_registry is BASELINE_CAPABILITY_REGISTRY
