from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from backend.agent_runtime.sandbox import (
    LOCAL_FILE_TRANSFORM_PROFILE_ID,
    ResolvedSandboxPath,
    SandboxDecisionCode,
    SandboxDisposition,
    SandboxOperation,
    SandboxPolicy,
    SandboxRelativePath,
    SandboxRootRef,
)

PROFILE_ID = LOCAL_FILE_TRANSFORM_PROFILE_ID
ROOT = SandboxRootRef(run_id="run-1", root_id="sandbox-root-1")
_DEFAULT_RESOLUTION = object()


def _resolved(path: str = "input/source.txt", **overrides: object) -> ResolvedSandboxPath:
    relative_path = SandboxRelativePath(path)
    values: dict[str, object] = {
        "root_ref": ROOT,
        "relative_path": relative_path,
        "canonical_path_token": "resolved-token-1",
        "exists": True,
        "is_file": True,
        "is_symlink": False,
        "is_within_root": True,
        "size_bytes": 10,
        "observed_extension": relative_path.extension,
        "observed_mime_type": "text/plain",
        "has_active_content": False,
        "is_executable_content": False,
    }
    values.update(overrides)
    return ResolvedSandboxPath(**values)  # type: ignore[arg-type]


def _evaluate(
    *,
    operation: SandboxOperation | str = SandboxOperation.READ,
    path: str = "input/source.txt",
    resolved: ResolvedSandboxPath | None | object = _DEFAULT_RESOLUTION,
    **overrides: object,
):
    values: dict[str, object] = {
        "profile_id": PROFILE_ID,
        "root_ref": ROOT,
        "operation": operation,
        "relative_path": path,
        "resolved_path": (
            _resolved(path) if resolved is _DEFAULT_RESOLUTION else resolved
        ),
    }
    values.update(overrides)
    return SandboxPolicy().evaluate(**values)  # type: ignore[arg-type]


def test_read_is_allowed_only_with_trusted_matching_metadata() -> None:
    decision = _evaluate()

    assert decision.disposition is SandboxDisposition.ALLOW
    assert decision.code is SandboxDecisionCode.ALLOW
    assert decision.relative_path == SandboxRelativePath("input/source.txt")
    assert decision.canonical_path_token == "resolved-token-1"


def test_write_and_create_are_allowed_with_bounded_declarations() -> None:
    write = _evaluate(
        operation=SandboxOperation.WRITE,
        path="output/report.pdf",
        resolved=_resolved(
            "output/report.pdf",
            observed_mime_type="application/pdf",
        ),
        declared_output_bytes=100,
        declared_mime_type="application/pdf",
    )
    create = _evaluate(
        operation=SandboxOperation.CREATE,
        path="output/report.pdf",
        resolved=_resolved(
            "output/report.pdf",
            exists=False,
            is_file=False,
            size_bytes=0,
            observed_mime_type=None,
        ),
        declared_output_bytes=100,
        declared_mime_type="application/pdf",
    )

    assert write.code is SandboxDecisionCode.ALLOW
    assert create.code is SandboxDecisionCode.ALLOW


def test_unknown_profile_is_denied_without_fallback() -> None:
    decision = _evaluate(profile_id="sandbox.missing.v1")

    assert decision.code is SandboxDecisionCode.UNKNOWN_PROFILE
    assert decision.disposition is SandboxDisposition.DENY


def test_execute_is_always_denied() -> None:
    decision = _evaluate(operation="EXECUTE")

    assert decision.code is SandboxDecisionCode.EXECUTION_FORBIDDEN


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ("/etc/passwd", SandboxDecisionCode.ABSOLUTE_PATH_FORBIDDEN),
        ("../secret", SandboxDecisionCode.TRAVERSAL_FORBIDDEN),
        ("\\\\server\\share\\file", SandboxDecisionCode.NETWORK_PATH_FORBIDDEN),
        ("a//b", SandboxDecisionCode.INVALID_RELATIVE_PATH),
    ],
)
def test_invalid_paths_are_denied_without_echoing_hostile_value(
    path: str,
    code: SandboxDecisionCode,
) -> None:
    decision = _evaluate(path=path, resolved=None)

    assert decision.code is code
    assert decision.relative_path is None
    assert path not in repr(decision)


def test_root_mismatch_and_failed_confinement_are_denied() -> None:
    other_root = SandboxRootRef(run_id="run-1", root_id="other-root")

    assert _evaluate(resolved=_resolved(root_ref=other_root)).code is (
        SandboxDecisionCode.ROOT_MISMATCH
    )
    assert _evaluate(resolved=_resolved(is_within_root=False)).code is (
        SandboxDecisionCode.ROOT_MISMATCH
    )


def test_path_mismatch_is_denied() -> None:
    decision = _evaluate(resolved=_resolved("input/other.txt"))

    assert decision.code is SandboxDecisionCode.PATH_MISMATCH


def test_symlink_is_denied_even_when_other_metadata_is_valid() -> None:
    decision = _evaluate(resolved=_resolved(is_symlink=True))

    assert decision.code is SandboxDecisionCode.SYMLINK_FORBIDDEN


@pytest.mark.parametrize("path", ["input/file.exe", "input/file.ps1", "input/file.cmd"])
def test_executable_extensions_are_denied(path: str) -> None:
    decision = _evaluate(path=path, resolved=_resolved(path))

    assert decision.code is SandboxDecisionCode.EXECUTION_FORBIDDEN


@pytest.mark.parametrize("path", ["input/file.docm", "input/file.lnk", "input/file.xlsm"])
def test_active_content_extensions_are_denied(path: str) -> None:
    decision = _evaluate(path=path, resolved=_resolved(path))

    assert decision.code is SandboxDecisionCode.ACTIVE_CONTENT_FORBIDDEN


def test_unlisted_extension_and_mime_are_denied() -> None:
    extension = _evaluate(path="input/data.csv", resolved=_resolved("input/data.csv"))
    mime = _evaluate(
        resolved=_resolved(observed_mime_type="application/octet-stream")
    )

    assert extension.code is SandboxDecisionCode.EXTENSION_FORBIDDEN
    assert mime.code is SandboxDecisionCode.MIME_FORBIDDEN


def test_missing_or_inconsistent_observed_metadata_is_denied() -> None:
    assert _evaluate(resolved=_resolved(observed_mime_type=None)).code is (
        SandboxDecisionCode.INVALID_METADATA
    )
    assert _evaluate(resolved=_resolved(observed_extension=".pdf")).code is (
        SandboxDecisionCode.INVALID_METADATA
    )
    assert _evaluate(resolved=_resolved(exists=False, is_file=False, size_bytes=0)).code is (
        SandboxDecisionCode.INVALID_METADATA
    )


def test_input_size_and_file_count_limits_are_enforced() -> None:
    too_large = _evaluate(resolved=_resolved(size_bytes=25 * 1024 * 1024 + 1))
    too_many = _evaluate(file_count=21)

    assert too_large.code is SandboxDecisionCode.INPUT_TOO_LARGE
    assert too_many.code is SandboxDecisionCode.FILE_COUNT_EXCEEDED


def test_output_size_mime_and_metadata_are_enforced() -> None:
    create_target = _resolved(
        "output/report.pdf",
        exists=False,
        is_file=False,
        size_bytes=0,
        observed_mime_type=None,
    )

    assert _evaluate(
        operation=SandboxOperation.CREATE,
        path="output/report.pdf",
        resolved=create_target,
        declared_output_bytes=50 * 1024 * 1024 + 1,
        declared_mime_type="application/pdf",
    ).code is SandboxDecisionCode.OUTPUT_TOO_LARGE
    assert _evaluate(
        operation=SandboxOperation.CREATE,
        path="output/report.pdf",
        resolved=create_target,
        declared_output_bytes=10,
        declared_mime_type="image/png",
    ).code is SandboxDecisionCode.MIME_FORBIDDEN
    assert _evaluate(
        operation=SandboxOperation.CREATE,
        path="output/report.pdf",
        resolved=create_target,
        declared_output_bytes=None,
        declared_mime_type="application/pdf",
    ).code is SandboxDecisionCode.INVALID_METADATA


def test_active_or_executable_content_facts_are_denied() -> None:
    assert _evaluate(resolved=_resolved(has_active_content=True)).code is (
        SandboxDecisionCode.ACTIVE_CONTENT_FORBIDDEN
    )
    assert _evaluate(resolved=_resolved(is_executable_content=True)).code is (
        SandboxDecisionCode.EXECUTION_FORBIDDEN
    )


def test_output_declarations_cannot_opt_into_active_or_executable_content() -> None:
    target = _resolved(
        "output/report.pdf",
        exists=False,
        is_file=False,
        size_bytes=0,
        observed_mime_type=None,
    )
    common = {
        "operation": SandboxOperation.CREATE,
        "path": "output/report.pdf",
        "resolved": target,
        "declared_output_bytes": 10,
        "declared_mime_type": "application/pdf",
    }

    assert _evaluate(**common, declares_active_content=True).code is (
        SandboxDecisionCode.ACTIVE_CONTENT_FORBIDDEN
    )
    assert _evaluate(**common, declares_executable_content=True).code is (
        SandboxDecisionCode.EXECUTION_FORBIDDEN
    )


def test_decision_is_immutable_and_data_only() -> None:
    decision = _evaluate()

    with pytest.raises(FrozenInstanceError):
        decision.code = SandboxDecisionCode.INVALID_METADATA  # type: ignore[misc]
    assert not hasattr(decision, "handler")
    assert not hasattr(decision, "absolute_path")
