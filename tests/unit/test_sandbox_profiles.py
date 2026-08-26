from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from backend.agent_runtime.sandbox import (
    BASELINE_SANDBOX_PROFILE_REGISTRY,
    LOCAL_FILE_TRANSFORM_PROFILE_ID,
    SandboxProfile,
    SandboxProfileRegistry,
    UnknownSandboxProfileError,
)


def _profile(**overrides: object) -> SandboxProfile:
    values: dict[str, object] = {
        "profile_id": "sandbox.test.v1",
        "allowed_input_extensions": (".txt",),
        "allowed_output_extensions": (".pdf",),
        "allowed_mime_types": ("text/plain", "application/pdf"),
        "max_input_bytes": 10,
        "max_output_bytes": 20,
        "max_file_count": 2,
        "allow_symlinks": False,
        "allow_active_content": False,
        "allow_executable_content": False,
        "allow_network_paths": False,
    }
    values.update(overrides)
    return SandboxProfile(**values)  # type: ignore[arg-type]


def test_baseline_profile_is_minimal_and_fail_closed() -> None:
    profile = BASELINE_SANDBOX_PROFILE_REGISTRY.get(
        LOCAL_FILE_TRANSFORM_PROFILE_ID
    )

    assert profile.allowed_input_extensions == (".docx", ".md", ".pdf", ".txt")
    assert profile.allowed_output_extensions == (".docx", ".pdf", ".txt")
    assert profile.allowed_mime_types == (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/markdown",
        "text/plain",
    )
    assert profile.max_input_bytes == 25 * 1024 * 1024
    assert profile.max_output_bytes == 50 * 1024 * 1024
    assert profile.max_file_count == 20
    assert not profile.allow_symlinks
    assert not profile.allow_active_content
    assert not profile.allow_executable_content
    assert not profile.allow_network_paths


def test_profile_has_no_root_or_execution_binding() -> None:
    assert {field.name for field in fields(SandboxProfile)} == {
        "profile_id",
        "allowed_input_extensions",
        "allowed_output_extensions",
        "allowed_mime_types",
        "max_input_bytes",
        "max_output_bytes",
        "max_file_count",
        "allow_symlinks",
        "allow_active_content",
        "allow_executable_content",
        "allow_network_paths",
    }


def test_profile_and_registry_are_immutable() -> None:
    profile = _profile()
    registry = SandboxProfileRegistry((profile,))

    with pytest.raises(FrozenInstanceError):
        profile.profile_id = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        registry._by_id[profile.profile_id] = profile  # type: ignore[index]


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("allowed_input_extensions", [".txt"]),
        ("allowed_input_extensions", ()),
        ("allowed_input_extensions", (".txt", ".txt")),
        ("allowed_input_extensions", ("txt",)),
        ("allowed_input_extensions", (".TXT",)),
        ("allowed_input_extensions", (".*",)),
        ("allowed_mime_types", ("text/*",)),
        ("allowed_mime_types", ("Text/Plain",)),
        ("allowed_mime_types", ("text/plain; charset=utf-8",)),
        ("allowed_mime_types", ("text/",)),
        ("allowed_mime_types", ("/plain",)),
    ],
)
def test_profile_rejects_invalid_allowlists(field_name: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _profile(**{field_name: value})


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("max_input_bytes", 0),
        ("max_output_bytes", -1),
        ("max_file_count", True),
        ("max_file_count", 1.5),
    ],
)
def test_profile_rejects_invalid_limits(field_name: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _profile(**{field_name: value})


def test_profile_rejects_non_boolean_security_flags() -> None:
    with pytest.raises(TypeError):
        _profile(allow_symlinks=1)


def test_registry_is_exact_match_and_closed_on_unknown_profile() -> None:
    profile = _profile()
    registry = SandboxProfileRegistry((profile,))

    assert registry.contains("sandbox.test.v1")
    assert registry.get("sandbox.test.v1") is profile
    assert registry.all() == (profile,)
    assert not registry.contains("sandbox.test")
    with pytest.raises(UnknownSandboxProfileError):
        registry.get("sandbox.missing.v1")


def test_registry_rejects_duplicate_profile_id() -> None:
    with pytest.raises(ValueError, match="duplicate profile_id"):
        SandboxProfileRegistry((_profile(), _profile()))


def test_registry_rejects_non_profile_values() -> None:
    with pytest.raises(TypeError):
        SandboxProfileRegistry((object(),))  # type: ignore[arg-type]
