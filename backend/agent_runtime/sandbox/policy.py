from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.sandbox.model import (
    ResolvedSandboxPath,
    SandboxOperation,
    SandboxPathValidationCode,
    SandboxRelativePath,
    SandboxRootRef,
    classify_sandbox_relative_path,
    is_normalized_mime_type,
)
from backend.agent_runtime.sandbox.profiles import (
    BASELINE_SANDBOX_PROFILE_REGISTRY,
    SandboxProfile,
    SandboxProfileRegistry,
    UnknownSandboxProfileError,
)
from backend.shared_kernel._strings import require_non_empty

_EXECUTABLE_EXTENSIONS = frozenset(
    {".bat", ".cmd", ".com", ".exe", ".hta", ".js", ".msi", ".ps1", ".scr", ".sh", ".vbs"}
)
_ACTIVE_CONTENT_EXTENSIONS = frozenset(
    {".desktop", ".docm", ".jar", ".lnk", ".pptm", ".url", ".xlsm"}
)


class SandboxDisposition(StrEnum):
    DENY = "DENY"
    ALLOW = "ALLOW"


class SandboxDecisionCode(StrEnum):
    ALLOW = "ALLOW"
    UNKNOWN_PROFILE = "UNKNOWN_PROFILE"
    INVALID_RELATIVE_PATH = "INVALID_RELATIVE_PATH"
    ABSOLUTE_PATH_FORBIDDEN = "ABSOLUTE_PATH_FORBIDDEN"
    TRAVERSAL_FORBIDDEN = "TRAVERSAL_FORBIDDEN"
    NETWORK_PATH_FORBIDDEN = "NETWORK_PATH_FORBIDDEN"
    SYMLINK_FORBIDDEN = "SYMLINK_FORBIDDEN"
    ROOT_MISMATCH = "ROOT_MISMATCH"
    PATH_MISMATCH = "PATH_MISMATCH"
    EXTENSION_FORBIDDEN = "EXTENSION_FORBIDDEN"
    MIME_FORBIDDEN = "MIME_FORBIDDEN"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    OUTPUT_TOO_LARGE = "OUTPUT_TOO_LARGE"
    FILE_COUNT_EXCEEDED = "FILE_COUNT_EXCEEDED"
    ACTIVE_CONTENT_FORBIDDEN = "ACTIVE_CONTENT_FORBIDDEN"
    EXECUTION_FORBIDDEN = "EXECUTION_FORBIDDEN"
    INVALID_METADATA = "INVALID_METADATA"


@dataclass(frozen=True, slots=True)
class SandboxDecision:
    disposition: SandboxDisposition
    code: SandboxDecisionCode
    profile_id: str
    root_ref: SandboxRootRef
    operation: SandboxOperation | None
    relative_path: SandboxRelativePath | None
    canonical_path_token: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, SandboxDisposition):
            raise TypeError("disposition must be a SandboxDisposition")
        if not isinstance(self.code, SandboxDecisionCode):
            raise TypeError("code must be a SandboxDecisionCode")
        require_non_empty(self.profile_id, "profile_id")
        if not isinstance(self.root_ref, SandboxRootRef):
            raise TypeError("root_ref must be a SandboxRootRef")
        if self.operation is not None and not isinstance(self.operation, SandboxOperation):
            raise TypeError("operation must be a SandboxOperation or None")
        if self.relative_path is not None and not isinstance(
            self.relative_path, SandboxRelativePath
        ):
            raise TypeError("relative_path must be a SandboxRelativePath or None")
        if self.canonical_path_token is not None:
            require_non_empty(self.canonical_path_token, "canonical_path_token")
        is_allow = self.disposition is SandboxDisposition.ALLOW
        if is_allow is not (self.code is SandboxDecisionCode.ALLOW):
            raise ValueError("ALLOW disposition and code must be equivalent")
        if is_allow and (
            self.operation is None
            or self.relative_path is None
            or self.canonical_path_token is None
        ):
            raise ValueError("ALLOW requires complete trusted resolution data")


@dataclass(frozen=True, slots=True)
class SandboxPolicy:
    profile_registry: SandboxProfileRegistry = BASELINE_SANDBOX_PROFILE_REGISTRY

    def __post_init__(self) -> None:
        if not isinstance(self.profile_registry, SandboxProfileRegistry):
            raise TypeError("profile_registry must be a SandboxProfileRegistry")

    def evaluate(
        self,
        *,
        profile_id: str,
        root_ref: SandboxRootRef,
        operation: SandboxOperation | str,
        relative_path: SandboxRelativePath | str,
        resolved_path: ResolvedSandboxPath | None,
        file_count: int = 1,
        declared_output_bytes: int | None = None,
        declared_mime_type: str | None = None,
        declares_active_content: bool = False,
        declares_executable_content: bool = False,
    ) -> SandboxDecision:
        require_non_empty(profile_id, "profile_id")
        if not isinstance(root_ref, SandboxRootRef):
            raise TypeError("root_ref must be a SandboxRootRef")
        try:
            profile = self.profile_registry.get(profile_id)
        except UnknownSandboxProfileError:
            return self._deny(
                profile_id,
                root_ref,
                SandboxDecisionCode.UNKNOWN_PROFILE,
            )

        normalized_operation = _coerce_operation(operation)
        if normalized_operation is None:
            code = (
                SandboxDecisionCode.EXECUTION_FORBIDDEN
                if operation == "EXECUTE"
                else SandboxDecisionCode.INVALID_METADATA
            )
            return self._deny(profile_id, root_ref, code)

        normalized_path, path_code = _coerce_relative_path(relative_path)
        if normalized_path is None:
            return self._deny(
                profile_id,
                root_ref,
                _decision_code_for_path(path_code),
                operation=normalized_operation,
            )

        if resolved_path is None or not isinstance(resolved_path, ResolvedSandboxPath):
            return self._deny(
                profile_id,
                root_ref,
                SandboxDecisionCode.INVALID_METADATA,
                operation=normalized_operation,
                relative_path=normalized_path,
            )
        if resolved_path.root_ref != root_ref:
            return self._deny_resolved(
                profile_id,
                root_ref,
                normalized_operation,
                normalized_path,
                resolved_path,
                SandboxDecisionCode.ROOT_MISMATCH,
            )
        if not resolved_path.is_within_root:
            return self._deny_resolved(
                profile_id,
                root_ref,
                normalized_operation,
                normalized_path,
                resolved_path,
                SandboxDecisionCode.ROOT_MISMATCH,
            )
        if resolved_path.relative_path != normalized_path:
            return self._deny_resolved(
                profile_id,
                root_ref,
                normalized_operation,
                normalized_path,
                resolved_path,
                SandboxDecisionCode.PATH_MISMATCH,
            )
        if resolved_path.is_symlink:
            return self._deny_resolved(
                profile_id,
                root_ref,
                normalized_operation,
                normalized_path,
                resolved_path,
                SandboxDecisionCode.SYMLINK_FORBIDDEN,
            )

        metadata_code = _validate_common_metadata(
            profile=profile,
            operation=normalized_operation,
            relative_path=normalized_path,
            resolved_path=resolved_path,
            file_count=file_count,
            declared_output_bytes=declared_output_bytes,
            declared_mime_type=declared_mime_type,
            declares_active_content=declares_active_content,
            declares_executable_content=declares_executable_content,
        )
        if metadata_code is not None:
            return self._deny_resolved(
                profile_id,
                root_ref,
                normalized_operation,
                normalized_path,
                resolved_path,
                metadata_code,
            )

        return SandboxDecision(
            disposition=SandboxDisposition.ALLOW,
            code=SandboxDecisionCode.ALLOW,
            profile_id=profile_id,
            root_ref=root_ref,
            operation=normalized_operation,
            relative_path=normalized_path,
            canonical_path_token=resolved_path.canonical_path_token,
        )

    @staticmethod
    def _deny(
        profile_id: str,
        root_ref: SandboxRootRef,
        code: SandboxDecisionCode,
        *,
        operation: SandboxOperation | None = None,
        relative_path: SandboxRelativePath | None = None,
        canonical_path_token: str | None = None,
    ) -> SandboxDecision:
        return SandboxDecision(
            disposition=SandboxDisposition.DENY,
            code=code,
            profile_id=profile_id,
            root_ref=root_ref,
            operation=operation,
            relative_path=relative_path,
            canonical_path_token=canonical_path_token,
        )

    @classmethod
    def _deny_resolved(
        cls,
        profile_id: str,
        root_ref: SandboxRootRef,
        operation: SandboxOperation,
        relative_path: SandboxRelativePath,
        resolved_path: ResolvedSandboxPath,
        code: SandboxDecisionCode,
    ) -> SandboxDecision:
        return cls._deny(
            profile_id,
            root_ref,
            code,
            operation=operation,
            relative_path=relative_path,
            canonical_path_token=resolved_path.canonical_path_token,
        )


def _coerce_operation(value: SandboxOperation | str) -> SandboxOperation | None:
    if isinstance(value, SandboxOperation):
        return value
    if not isinstance(value, str):
        return None
    try:
        return SandboxOperation(value)
    except ValueError:
        return None


def _coerce_relative_path(
    value: SandboxRelativePath | str,
) -> tuple[SandboxRelativePath | None, SandboxPathValidationCode]:
    if isinstance(value, SandboxRelativePath):
        return value, SandboxPathValidationCode.VALID
    code = classify_sandbox_relative_path(value)
    if code is not SandboxPathValidationCode.VALID:
        return None, code
    if not isinstance(value, str):
        return None, SandboxPathValidationCode.INVALID_RELATIVE_PATH
    return SandboxRelativePath(value), code


def _decision_code_for_path(code: SandboxPathValidationCode) -> SandboxDecisionCode:
    if code is SandboxPathValidationCode.ABSOLUTE_PATH_FORBIDDEN:
        return SandboxDecisionCode.ABSOLUTE_PATH_FORBIDDEN
    if code is SandboxPathValidationCode.TRAVERSAL_FORBIDDEN:
        return SandboxDecisionCode.TRAVERSAL_FORBIDDEN
    if code is SandboxPathValidationCode.NETWORK_PATH_FORBIDDEN:
        return SandboxDecisionCode.NETWORK_PATH_FORBIDDEN
    return SandboxDecisionCode.INVALID_RELATIVE_PATH


def _validate_common_metadata(
    *,
    profile: SandboxProfile,
    operation: SandboxOperation,
    relative_path: SandboxRelativePath,
    resolved_path: ResolvedSandboxPath,
    file_count: int,
    declared_output_bytes: int | None,
    declared_mime_type: str | None,
    declares_active_content: bool,
    declares_executable_content: bool,
) -> SandboxDecisionCode | None:
    if not isinstance(file_count, int) or isinstance(file_count, bool) or file_count <= 0:
        return SandboxDecisionCode.INVALID_METADATA
    if file_count > profile.max_file_count:
        return SandboxDecisionCode.FILE_COUNT_EXCEEDED
    if not isinstance(declares_active_content, bool) or not isinstance(
        declares_executable_content, bool
    ):
        return SandboxDecisionCode.INVALID_METADATA

    extension = relative_path.extension
    if extension in _EXECUTABLE_EXTENSIONS:
        return SandboxDecisionCode.EXECUTION_FORBIDDEN
    if extension in _ACTIVE_CONTENT_EXTENSIONS:
        return SandboxDecisionCode.ACTIVE_CONTENT_FORBIDDEN

    if operation is SandboxOperation.READ:
        return _validate_read_metadata(profile, relative_path, resolved_path)
    return _validate_output_metadata(
        profile=profile,
        operation=operation,
        relative_path=relative_path,
        resolved_path=resolved_path,
        declared_output_bytes=declared_output_bytes,
        declared_mime_type=declared_mime_type,
        declares_active_content=declares_active_content,
        declares_executable_content=declares_executable_content,
    )


def _validate_read_metadata(
    profile: SandboxProfile,
    relative_path: SandboxRelativePath,
    resolved_path: ResolvedSandboxPath,
) -> SandboxDecisionCode | None:
    if not resolved_path.exists or not resolved_path.is_file:
        return SandboxDecisionCode.INVALID_METADATA
    if resolved_path.is_executable_content:
        return SandboxDecisionCode.EXECUTION_FORBIDDEN
    if resolved_path.has_active_content and not profile.allow_active_content:
        return SandboxDecisionCode.ACTIVE_CONTENT_FORBIDDEN
    if (
        resolved_path.observed_extension is None
        or resolved_path.observed_extension != relative_path.extension
    ):
        return SandboxDecisionCode.INVALID_METADATA
    if resolved_path.observed_extension not in profile.allowed_input_extensions:
        return SandboxDecisionCode.EXTENSION_FORBIDDEN
    if resolved_path.observed_mime_type is None:
        return SandboxDecisionCode.INVALID_METADATA
    if resolved_path.observed_mime_type not in profile.allowed_mime_types:
        return SandboxDecisionCode.MIME_FORBIDDEN
    if resolved_path.size_bytes > profile.max_input_bytes:
        return SandboxDecisionCode.INPUT_TOO_LARGE
    return None


def _validate_output_metadata(
    *,
    profile: SandboxProfile,
    operation: SandboxOperation,
    relative_path: SandboxRelativePath,
    resolved_path: ResolvedSandboxPath,
    declared_output_bytes: int | None,
    declared_mime_type: str | None,
    declares_active_content: bool,
    declares_executable_content: bool,
) -> SandboxDecisionCode | None:
    if (
        resolved_path.observed_extension is not None
        and resolved_path.observed_extension != relative_path.extension
    ):
        return SandboxDecisionCode.INVALID_METADATA
    if operation is SandboxOperation.WRITE:
        if not resolved_path.exists or not resolved_path.is_file:
            return SandboxDecisionCode.INVALID_METADATA
    elif resolved_path.exists:
        return SandboxDecisionCode.INVALID_METADATA
    if relative_path.extension not in profile.allowed_output_extensions:
        return SandboxDecisionCode.EXTENSION_FORBIDDEN
    if (
        declared_output_bytes is None
        or not isinstance(declared_output_bytes, int)
        or isinstance(declared_output_bytes, bool)
        or declared_output_bytes < 0
    ):
        return SandboxDecisionCode.INVALID_METADATA
    if declared_output_bytes > profile.max_output_bytes:
        return SandboxDecisionCode.OUTPUT_TOO_LARGE
    if not is_normalized_mime_type(declared_mime_type):
        return SandboxDecisionCode.INVALID_METADATA
    if declared_mime_type not in profile.allowed_mime_types:
        return SandboxDecisionCode.MIME_FORBIDDEN
    if declares_executable_content:
        return SandboxDecisionCode.EXECUTION_FORBIDDEN
    if declares_active_content and not profile.allow_active_content:
        return SandboxDecisionCode.ACTIVE_CONTENT_FORBIDDEN
    return None
