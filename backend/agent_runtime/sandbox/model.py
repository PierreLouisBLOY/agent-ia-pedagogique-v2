from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from backend.shared_kernel._strings import require_non_empty

MAX_SANDBOX_PATH_LENGTH = 1024
MAX_SANDBOX_PATH_SEGMENTS = 32
MAX_SANDBOX_PATH_SEGMENT_LENGTH = 255
MAX_SANDBOX_METADATA_BYTES = (1 << 63) - 1

_URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_MIME_TYPE = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$"
)
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


class SandboxPathValidationCode(StrEnum):
    VALID = "VALID"
    INVALID_RELATIVE_PATH = "INVALID_RELATIVE_PATH"
    ABSOLUTE_PATH_FORBIDDEN = "ABSOLUTE_PATH_FORBIDDEN"
    TRAVERSAL_FORBIDDEN = "TRAVERSAL_FORBIDDEN"
    NETWORK_PATH_FORBIDDEN = "NETWORK_PATH_FORBIDDEN"


class SandboxOperation(StrEnum):
    READ = "READ"
    WRITE = "WRITE"
    CREATE = "CREATE"


def classify_sandbox_relative_path(value: object) -> SandboxPathValidationCode:
    if not isinstance(value, str) or not value:
        return SandboxPathValidationCode.INVALID_RELATIVE_PATH
    if len(value) > MAX_SANDBOX_PATH_LENGTH:
        return SandboxPathValidationCode.INVALID_RELATIVE_PATH
    if value.startswith(("//", "\\\\")):
        return SandboxPathValidationCode.NETWORK_PATH_FORBIDDEN
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        return SandboxPathValidationCode.ABSOLUTE_PATH_FORBIDDEN
    scheme_match = _URI_SCHEME.match(value)
    if scheme_match is not None:
        scheme = value[: scheme_match.end() - 1].casefold()
        if scheme in {"http", "https", "ftp", "smb"}:
            return SandboxPathValidationCode.NETWORK_PATH_FORBIDDEN
        if scheme == "file":
            return SandboxPathValidationCode.ABSOLUTE_PATH_FORBIDDEN
        return SandboxPathValidationCode.INVALID_RELATIVE_PATH
    if "\\" in value:
        return SandboxPathValidationCode.INVALID_RELATIVE_PATH
    if any(unicodedata.category(character).startswith("C") for character in value):
        return SandboxPathValidationCode.INVALID_RELATIVE_PATH
    if unicodedata.normalize("NFC", value) != value:
        return SandboxPathValidationCode.INVALID_RELATIVE_PATH
    if ":" in value or "~" in value or any(
        character in '<>"|?*' for character in value
    ):
        return SandboxPathValidationCode.INVALID_RELATIVE_PATH

    segments = value.split("/")
    if len(segments) > MAX_SANDBOX_PATH_SEGMENTS:
        return SandboxPathValidationCode.INVALID_RELATIVE_PATH
    if any(not segment for segment in segments):
        return SandboxPathValidationCode.INVALID_RELATIVE_PATH
    if any(segment == ".." for segment in segments):
        return SandboxPathValidationCode.TRAVERSAL_FORBIDDEN
    if any(segment == "." for segment in segments):
        return SandboxPathValidationCode.INVALID_RELATIVE_PATH
    for segment in segments:
        if len(segment) > MAX_SANDBOX_PATH_SEGMENT_LENGTH:
            return SandboxPathValidationCode.INVALID_RELATIVE_PATH
        if segment != segment.strip() or segment.endswith("."):
            return SandboxPathValidationCode.INVALID_RELATIVE_PATH
        windows_stem = segment.split(".", maxsplit=1)[0].upper()
        if windows_stem in _WINDOWS_RESERVED_NAMES:
            return SandboxPathValidationCode.INVALID_RELATIVE_PATH
    return SandboxPathValidationCode.VALID


@dataclass(frozen=True, slots=True)
class SandboxRelativePath:
    value: str

    def __post_init__(self) -> None:
        code = classify_sandbox_relative_path(self.value)
        if code is not SandboxPathValidationCode.VALID:
            raise ValueError(code.value)

    @property
    def segments(self) -> tuple[str, ...]:
        return tuple(self.value.split("/"))

    @property
    def extension(self) -> str:
        filename = self.segments[-1]
        separator_index = filename.rfind(".")
        if separator_index <= 0:
            return ""
        return filename[separator_index:].casefold()


def _require_opaque_id(value: str, field_name: str, *, max_length: int) -> None:
    require_non_empty(value, field_name)
    if len(value) > max_length or _OPAQUE_ID.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be an opaque identifier")


@dataclass(frozen=True, slots=True)
class SandboxRootRef:
    run_id: str
    root_id: str

    def __post_init__(self) -> None:
        _require_opaque_id(self.run_id, "run_id", max_length=128)
        _require_opaque_id(self.root_id, "root_id", max_length=128)


@dataclass(frozen=True, slots=True)
class ResolvedSandboxPath:
    """Trusted adapter evidence represented without an operating-system path."""

    root_ref: SandboxRootRef
    relative_path: SandboxRelativePath
    canonical_path_token: str
    exists: bool
    is_file: bool
    is_symlink: bool
    is_within_root: bool
    size_bytes: int
    observed_extension: str | None
    observed_mime_type: str | None
    has_active_content: bool = False
    is_executable_content: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.root_ref, SandboxRootRef):
            raise TypeError("root_ref must be a SandboxRootRef")
        if not isinstance(self.relative_path, SandboxRelativePath):
            raise TypeError("relative_path must be a SandboxRelativePath")
        _require_opaque_id(
            self.canonical_path_token,
            "canonical_path_token",
            max_length=256,
        )
        boolean_fields = (
            ("exists", self.exists),
            ("is_file", self.is_file),
            ("is_symlink", self.is_symlink),
            ("is_within_root", self.is_within_root),
            ("has_active_content", self.has_active_content),
            ("is_executable_content", self.is_executable_content),
        )
        for field_name, value in boolean_fields:
            if not isinstance(value, bool):
                raise TypeError(f"{field_name} must be a bool")
        if not isinstance(self.size_bytes, int) or isinstance(self.size_bytes, bool):
            raise TypeError("size_bytes must be an int")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be >= 0")
        if self.size_bytes > MAX_SANDBOX_METADATA_BYTES:
            raise ValueError("size_bytes exceeds the metadata bound")
        if self.observed_extension is not None:
            _validate_extension(self.observed_extension, "observed_extension")
        if self.observed_mime_type is not None:
            _validate_mime_type(self.observed_mime_type, "observed_mime_type")
        if not self.exists and (
            self.is_file
            or self.is_symlink
            or self.size_bytes != 0
            or self.has_active_content
            or self.is_executable_content
        ):
            raise ValueError("non-existent paths cannot carry observed file state")


def _validate_extension(value: str, field_name: str) -> None:
    require_non_empty(value, field_name)
    if (
        value != value.casefold()
        or not value.startswith(".")
        or len(value) < 2
        or len(value) > 16
        or any(not (character.isalnum() or character in {".", "_", "-"}) for character in value)
    ):
        raise ValueError(f"{field_name} must be a normalized extension")


def _validate_mime_type(value: str, field_name: str) -> None:
    require_non_empty(value, field_name)
    if (
        value != value.casefold()
        or len(value) > 127
        or _MIME_TYPE.fullmatch(value) is None
        or "*" in value
        or ";" in value
        or any(character.isspace() or ord(character) < 32 for character in value)
    ):
        raise ValueError(f"{field_name} must be a normalized MIME type")


def is_normalized_mime_type(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        _validate_mime_type(value, "mime_type")
    except (TypeError, ValueError):
        return False
    return True
