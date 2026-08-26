from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from backend.agent_runtime.sandbox import (
    MAX_SANDBOX_PATH_LENGTH,
    ResolvedSandboxPath,
    SandboxPathValidationCode,
    SandboxRelativePath,
    SandboxRootRef,
    classify_sandbox_relative_path,
)


@pytest.mark.parametrize(
    "value",
    [
        "document.txt",
        "inputs/source.md",
        "résultats/final.pdf",
        "folder/file name.docx",
    ],
)
def test_relative_path_accepts_only_canonical_relative_forms(value: str) -> None:
    path = SandboxRelativePath(value)

    assert path.value == value
    assert "/".join(path.segments) == value


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("/etc/passwd", SandboxPathValidationCode.ABSOLUTE_PATH_FORBIDDEN),
        ("C:/Windows/system.ini", SandboxPathValidationCode.ABSOLUTE_PATH_FORBIDDEN),
        ("C:\\Windows\\system.ini", SandboxPathValidationCode.ABSOLUTE_PATH_FORBIDDEN),
        ("\\\\server\\share\\file", SandboxPathValidationCode.NETWORK_PATH_FORBIDDEN),
        ("//server/share/file", SandboxPathValidationCode.NETWORK_PATH_FORBIDDEN),
        ("../secret", SandboxPathValidationCode.TRAVERSAL_FORBIDDEN),
        ("a/../../secret", SandboxPathValidationCode.TRAVERSAL_FORBIDDEN),
        ("./file", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("a//b", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("~/.ssh/id_rsa", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("file:///etc/passwd", SandboxPathValidationCode.ABSOLUTE_PATH_FORBIDDEN),
        ("http://host/a", SandboxPathValidationCode.NETWORK_PATH_FORBIDDEN),
        ("data:text/plain,a", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("folder\\file.txt", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("folder/NUL.txt", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("folder/com1", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("folder/file.txt.", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("folder/file.txt ", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("folder/ file.txt", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("folder/file?.txt", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("folder/file*.txt", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("folder/file\x00.txt", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("folder/file\x1f.txt", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("folder/file\u0085.txt", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
        ("", SandboxPathValidationCode.INVALID_RELATIVE_PATH),
    ],
)
def test_relative_path_rejects_hostile_or_ambiguous_forms(
    value: str,
    code: SandboxPathValidationCode,
) -> None:
    assert classify_sandbox_relative_path(value) is code
    with pytest.raises(ValueError, match=code.value):
        SandboxRelativePath(value)


def test_relative_path_rejects_non_canonical_unicode() -> None:
    decomposed = "re\N{COMBINING ACUTE ACCENT}sultat.pdf"

    assert classify_sandbox_relative_path(decomposed) is (
        SandboxPathValidationCode.INVALID_RELATIVE_PATH
    )


def test_relative_path_has_bounded_length_and_segment_count() -> None:
    assert classify_sandbox_relative_path("a" * (MAX_SANDBOX_PATH_LENGTH + 1)) is (
        SandboxPathValidationCode.INVALID_RELATIVE_PATH
    )
    assert classify_sandbox_relative_path("/".join("a" for _ in range(33))) is (
        SandboxPathValidationCode.INVALID_RELATIVE_PATH
    )
    assert classify_sandbox_relative_path("a" * 256) is (
        SandboxPathValidationCode.INVALID_RELATIVE_PATH
    )


def test_relative_path_extension_is_lexical_and_case_folded() -> None:
    assert SandboxRelativePath("output/REPORT.PDF").extension == ".pdf"
    assert SandboxRelativePath("output/README").extension == ""


def test_relative_path_is_immutable() -> None:
    path = SandboxRelativePath("output/report.pdf")

    with pytest.raises(FrozenInstanceError):
        path.value = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("run_id", "root_id"),
    [
        ("run/absolute", "root-1"),
        ("run-1", "C:/root"),
        ("run-1", "../root"),
        ("run-1", "root with spaces"),
    ],
)
def test_root_ref_contains_only_opaque_identifiers(run_id: str, root_id: str) -> None:
    with pytest.raises(ValueError):
        SandboxRootRef(run_id=run_id, root_id=root_id)


def test_resolved_path_rejects_absolute_or_path_like_tokens() -> None:
    with pytest.raises(ValueError, match="opaque identifier"):
        _resolved(canonical_path_token="C:/sandbox/file.txt")


def test_resolved_path_rejects_impossible_nonexistent_metadata() -> None:
    with pytest.raises(ValueError, match="non-existent paths"):
        _resolved(exists=False, is_file=True)


def _resolved(**overrides: object) -> ResolvedSandboxPath:
    values: dict[str, object] = {
        "root_ref": SandboxRootRef(run_id="run-1", root_id="root-1"),
        "relative_path": SandboxRelativePath("input/file.txt"),
        "canonical_path_token": "path-token-1",
        "exists": True,
        "is_file": True,
        "is_symlink": False,
        "is_within_root": True,
        "size_bytes": 10,
        "observed_extension": ".txt",
        "observed_mime_type": "text/plain",
    }
    values.update(overrides)
    return ResolvedSandboxPath(**values)  # type: ignore[arg-type]
