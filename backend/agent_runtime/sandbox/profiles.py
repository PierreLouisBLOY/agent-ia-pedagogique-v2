from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from backend.agent_runtime.sandbox.model import _validate_extension, _validate_mime_type
from backend.shared_kernel._strings import require_non_empty

LOCAL_FILE_TRANSFORM_PROFILE_ID: Final[str] = "sandbox.local_file_transform.v1"
MEBIBYTE: Final[int] = 1024 * 1024


@dataclass(frozen=True, slots=True)
class SandboxProfile:
    profile_id: str
    allowed_input_extensions: tuple[str, ...]
    allowed_output_extensions: tuple[str, ...]
    allowed_mime_types: tuple[str, ...]
    max_input_bytes: int
    max_output_bytes: int
    max_file_count: int
    allow_symlinks: bool
    allow_active_content: bool
    allow_executable_content: bool
    allow_network_paths: bool

    def __post_init__(self) -> None:
        require_non_empty(self.profile_id, "profile_id")
        _validate_unique_tuple(
            self.allowed_input_extensions,
            "allowed_input_extensions",
            _validate_extension,
        )
        _validate_unique_tuple(
            self.allowed_output_extensions,
            "allowed_output_extensions",
            _validate_extension,
        )
        _validate_unique_tuple(
            self.allowed_mime_types,
            "allowed_mime_types",
            _validate_mime_type,
        )
        limits = (
            ("max_input_bytes", self.max_input_bytes),
            ("max_output_bytes", self.max_output_bytes),
            ("max_file_count", self.max_file_count),
        )
        for field_name, value in limits:
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{field_name} must be an int")
            if value <= 0:
                raise ValueError(f"{field_name} must be > 0")
        security_flags = (
            ("allow_symlinks", self.allow_symlinks),
            ("allow_active_content", self.allow_active_content),
            ("allow_executable_content", self.allow_executable_content),
            ("allow_network_paths", self.allow_network_paths),
        )
        for field_name, value in security_flags:
            if not isinstance(value, bool):
                raise TypeError(f"{field_name} must be a bool")


def _validate_unique_tuple(
    values: tuple[str, ...],
    field_name: str,
    validator: object,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    if not values:
        raise ValueError(f"{field_name} must not be empty")
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must contain unique values")
    if not callable(validator):
        raise TypeError("validator must be callable")
    for value in values:
        validator(value, field_name)


class UnknownSandboxProfileError(LookupError):
    def __init__(self, profile_id: str) -> None:
        require_non_empty(profile_id, "profile_id")
        self.profile_id = profile_id
        super().__init__(f"unknown sandbox profile: {profile_id}")


@dataclass(frozen=True, slots=True)
class SandboxProfileRegistry:
    _profiles: tuple[SandboxProfile, ...]
    _by_id: MappingProxyType[str, SandboxProfile]

    def __init__(self, profiles: Iterable[SandboxProfile]) -> None:
        normalized = tuple(profiles)
        if any(not isinstance(item, SandboxProfile) for item in normalized):
            raise TypeError("profiles must contain SandboxProfile values")
        profile_ids = tuple(profile.profile_id for profile in normalized)
        if len(set(profile_ids)) != len(profile_ids):
            raise ValueError("duplicate profile_id in registry")
        object.__setattr__(self, "_profiles", normalized)
        object.__setattr__(
            self,
            "_by_id",
            MappingProxyType({profile.profile_id: profile for profile in normalized}),
        )

    def get(self, profile_id: str) -> SandboxProfile:
        require_non_empty(profile_id, "profile_id")
        try:
            return self._by_id[profile_id]
        except KeyError as error:
            raise UnknownSandboxProfileError(profile_id) from error

    def contains(self, profile_id: str) -> bool:
        require_non_empty(profile_id, "profile_id")
        return profile_id in self._by_id

    def all(self) -> tuple[SandboxProfile, ...]:
        return self._profiles


BASELINE_SANDBOX_PROFILE_REGISTRY: Final = SandboxProfileRegistry(
    (
        SandboxProfile(
            profile_id=LOCAL_FILE_TRANSFORM_PROFILE_ID,
            allowed_input_extensions=(".docx", ".md", ".pdf", ".txt"),
            allowed_output_extensions=(".docx", ".pdf", ".txt"),
            allowed_mime_types=(
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "text/markdown",
                "text/plain",
            ),
            max_input_bytes=25 * MEBIBYTE,
            max_output_bytes=50 * MEBIBYTE,
            max_file_count=20,
            allow_symlinks=False,
            allow_active_content=False,
            allow_executable_content=False,
            allow_network_paths=False,
        ),
    )
)
