from __future__ import annotations

from backend.agent_runtime.registry import BASELINE_TOOL_REGISTRY, ToolEffectClass
from backend.agent_runtime.sandbox import (
    BASELINE_SANDBOX_PROFILE_REGISTRY,
    LOCAL_FILE_TRANSFORM_PROFILE_ID,
)


def test_every_local_file_transform_binds_to_an_existing_sandbox_profile() -> None:
    descriptors = tuple(
        descriptor
        for descriptor in BASELINE_TOOL_REGISTRY.all()
        if descriptor.effect_class is ToolEffectClass.LOCAL_FILE_TRANSFORM
    )

    assert descriptors
    assert all(descriptor.sandbox_profile_id is not None for descriptor in descriptors)
    assert all(
        BASELINE_SANDBOX_PROFILE_REGISTRY.contains(descriptor.sandbox_profile_id)
        for descriptor in descriptors
        if descriptor.sandbox_profile_id is not None
    )


def test_render_and_convert_bind_to_the_canonical_local_transform_profile() -> None:
    assert {
        descriptor.tool_id: descriptor.sandbox_profile_id
        for descriptor in BASELINE_TOOL_REGISTRY.all()
    } == {
        "tool.render_document": LOCAL_FILE_TRANSFORM_PROFILE_ID,
        "tool.convert_format": LOCAL_FILE_TRANSFORM_PROFILE_ID,
    }


def test_sandbox_registry_does_not_import_or_mutate_tool_registry() -> None:
    profile = BASELINE_SANDBOX_PROFILE_REGISTRY.get(LOCAL_FILE_TRANSFORM_PROFILE_ID)

    assert profile.profile_id == LOCAL_FILE_TRANSFORM_PROFILE_ID
    assert len(BASELINE_TOOL_REGISTRY.all()) == 2
