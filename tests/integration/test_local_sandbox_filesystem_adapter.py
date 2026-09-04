from __future__ import annotations

from pathlib import Path

import pytest

from backend.adapters.outbound.filesystem import LocalSandboxFilesystemAdapter
from backend.agent_runtime.sandbox import (
    LOCAL_FILE_TRANSFORM_PROFILE_ID,
    SandboxDisposition,
    SandboxFilesystemPort,
    SandboxOperation,
    SandboxPolicy,
    SandboxRelativePath,
    SandboxRootRef,
)
from backend.infrastructure.filesystem import LocalFileSecurityCode, LocalFileSecurityError

ROOT_REF = SandboxRootRef("run-local-adapter", "root-local-adapter")


def _adapter(root: Path) -> LocalSandboxFilesystemAdapter:
    return LocalSandboxFilesystemAdapter({ROOT_REF: root.resolve()})


def test_concrete_adapter_satisfies_port_and_supplies_trusted_metadata(
    tmp_path: Path,
) -> None:
    root = (tmp_path / "sandbox").resolve()
    root.mkdir()
    source = root / "source.md"
    source.write_text("# Titre\n", encoding="utf-8")
    adapter = _adapter(root)
    relative = SandboxRelativePath("source.md")

    resolved = adapter.resolve(root_ref=ROOT_REF, relative_path=relative)
    inspected = adapter.inspect(resolved_path=resolved)
    decision = SandboxPolicy().evaluate(
        profile_id=LOCAL_FILE_TRANSFORM_PROFILE_ID,
        root_ref=ROOT_REF,
        operation=SandboxOperation.READ,
        relative_path=relative,
        resolved_path=inspected,
    )

    assert isinstance(adapter, SandboxFilesystemPort)
    assert inspected.exists is True
    assert inspected.is_file is True
    assert inspected.is_symlink is False
    assert inspected.is_within_root is True
    assert inspected.observed_extension == ".md"
    assert inspected.observed_mime_type == "text/markdown"
    assert decision.disposition is SandboxDisposition.ALLOW


def test_adapter_rejects_extension_content_mismatch_and_size_overflow(
    tmp_path: Path,
) -> None:
    root = (tmp_path / "sandbox").resolve()
    root.mkdir()
    (root / "fake.pdf").write_text("not a pdf", encoding="utf-8")
    (root / "large.txt").write_bytes(b"x" * 33)
    adapter = _adapter(root)

    fake = adapter.resolve(
        root_ref=ROOT_REF, relative_path=SandboxRelativePath("fake.pdf")
    )
    fake_decision = SandboxPolicy().evaluate(
        profile_id=LOCAL_FILE_TRANSFORM_PROFILE_ID,
        root_ref=ROOT_REF,
        operation=SandboxOperation.READ,
        relative_path=SandboxRelativePath("fake.pdf"),
        resolved_path=fake,
    )
    assert fake.observed_mime_type is None
    assert fake_decision.disposition is SandboxDisposition.DENY

    with pytest.raises(LocalFileSecurityError) as raised:
        adapter.read_bytes(
            root_ref=ROOT_REF,
            relative_path=SandboxRelativePath("large.txt"),
            maximum_bytes=32,
        )
    assert raised.value.code is LocalFileSecurityCode.FILE_TOO_LARGE


def test_adapter_atomically_publishes_and_post_inspects_declared_output(
    tmp_path: Path,
) -> None:
    root = (tmp_path / "sandbox").resolve()
    root.mkdir()
    adapter = _adapter(root)
    output = SandboxRelativePath("output/result.txt")

    resolved = adapter.publish_bytes(
        root_ref=ROOT_REF,
        relative_path=output,
        payload=b"safe output\n",
        maximum_bytes=1024,
    )
    decision = SandboxPolicy().evaluate(
        profile_id=LOCAL_FILE_TRANSFORM_PROFILE_ID,
        root_ref=ROOT_REF,
        operation=SandboxOperation.WRITE,
        relative_path=output,
        resolved_path=resolved,
        declared_output_bytes=resolved.size_bytes,
        declared_mime_type=resolved.observed_mime_type,
    )

    assert adapter.read_bytes(
        root_ref=ROOT_REF,
        relative_path=output,
        maximum_bytes=1024,
    ) == b"safe output\n"
    assert resolved.observed_mime_type == "text/plain"
    assert decision.disposition is SandboxDisposition.ALLOW
    assert tuple((root / "output").glob("*.tmp")) == ()


def test_post_inspection_rejects_a_changed_file_identity(tmp_path: Path) -> None:
    root = (tmp_path / "sandbox").resolve()
    root.mkdir()
    source = root / "source.txt"
    source.write_text("first", encoding="utf-8")
    adapter = _adapter(root)
    relative = SandboxRelativePath("source.txt")
    resolved = adapter.resolve(root_ref=ROOT_REF, relative_path=relative)
    source.write_text("changed state", encoding="utf-8")

    with pytest.raises(LocalFileSecurityError) as raised:
        adapter.inspect(resolved_path=resolved)

    assert raised.value.code is LocalFileSecurityCode.PATH_CHANGED
