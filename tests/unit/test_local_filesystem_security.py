from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from backend.infrastructure.filesystem import (
    LocalFileSecurityCode,
    LocalFileSecurityError,
    PermissionStatus,
    atomic_publish_fresh,
    atomic_replace_checked,
    capture_secure_path,
    ensure_private_directory,
    harden_private_file,
    inspect_permission_status,
    read_file_nofollow,
    resolve_secure_path,
    security,
)


def test_lexical_traversal_outside_allowed_root_is_rejected(tmp_path: Path) -> None:
    root = (tmp_path / "root").resolve()
    root.mkdir()

    with pytest.raises(LocalFileSecurityError) as raised:
        resolve_secure_path(root / "nested" / ".." / ".." / "escape.txt", allowed_root=root)

    assert raised.value.code is LocalFileSecurityCode.OUTSIDE_ALLOWED_ROOT
    assert str(tmp_path) not in str(raised.value)


def test_synced_or_g_drive_runtime_roots_are_rejected_on_windows() -> None:
    if os.name != "nt":
        pytest.skip("Windows drive policy")

    for candidate in (Path("G:/ProjetV2"), Path("C:/Users/test/OneDrive/ProjetV2")):
        with pytest.raises(LocalFileSecurityError) as raised:
            security.assert_local_data_root(candidate)
        assert raised.value.code is LocalFileSecurityCode.NON_LOCAL_ROOT


def test_symlink_file_and_parent_are_rejected_when_supported(tmp_path: Path) -> None:
    root = (tmp_path / "root").resolve()
    outside = (tmp_path / "outside").resolve()
    root.mkdir()
    outside.mkdir()
    target = outside / "target.txt"
    target.write_text("outside", encoding="utf-8")
    file_link = root / "file.txt"
    parent_link = root / "linked-parent"
    try:
        file_link.symlink_to(target)
        parent_link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links are unavailable")

    for candidate in (file_link, parent_link / "target.txt"):
        with pytest.raises(LocalFileSecurityError) as raised:
            resolve_secure_path(candidate, allowed_root=root)
        assert raised.value.code is LocalFileSecurityCode.PATH_REDIRECTION_FORBIDDEN


def test_windows_junction_parent_is_rejected_when_supported(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("Windows junction policy")
    root = (tmp_path / "root").resolve()
    outside = (tmp_path / "outside").resolve()
    root.mkdir()
    outside.mkdir()
    junction = root / "junction"
    completed = subprocess.run(
        ("cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        pytest.skip("junction creation is unavailable")
    try:
        with pytest.raises(LocalFileSecurityError) as raised:
            resolve_secure_path(junction / "file.txt", allowed_root=root)
        assert raised.value.code is LocalFileSecurityCode.PATH_REDIRECTION_FORBIDDEN
    finally:
        junction.rmdir()


def test_private_directory_and_file_receive_owner_only_policy(tmp_path: Path) -> None:
    root = (tmp_path / "private-root").resolve()
    assert ensure_private_directory(root, allowed_root=root) is PermissionStatus.PRIVATE_OWNER_ONLY
    payload = root / "data.txt"
    payload.write_text("private", encoding="utf-8")

    assert harden_private_file(payload, allowed_root=root) is PermissionStatus.PRIVATE_OWNER_ONLY
    assert (
        inspect_permission_status(payload, allowed_root=root)
        is PermissionStatus.PRIVATE_OWNER_ONLY
    )
    if os.name != "nt":
        assert os.stat(root).st_mode & 0o077 == 0
        assert os.stat(payload).st_mode & 0o077 == 0


def test_nofollow_read_detects_replacement_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path.resolve()
    requested = root / "requested.txt"
    replacement = root / "replacement.txt"
    requested.write_text("expected", encoding="utf-8")
    replacement.write_text("attacker", encoding="utf-8")
    original_open = security.os.open
    raced = False

    def race_open(path: str | bytes | os.PathLike[str], flags: int, mode: int = 0o777) -> int:
        nonlocal raced
        if not raced and Path(path) == requested:
            raced = True
            requested.unlink()
            os.link(replacement, requested)
        return original_open(path, flags, mode)

    monkeypatch.setattr(security.os, "open", race_open)

    with pytest.raises(LocalFileSecurityError) as raised:
        read_file_nofollow(requested, allowed_root=root, maximum_bytes=100)

    assert raised.value.code is LocalFileSecurityCode.PATH_CHANGED


def test_atomic_fresh_publication_preserves_race_winner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path.resolve()
    source = root / "source.tmp"
    destination = root / "final.txt"
    source.write_bytes(b"ours")
    original_link = security.os.link

    def race_link(source_path: Path, destination_path: Path) -> None:
        if destination_path == destination:
            destination.write_bytes(b"winner")
            raise FileExistsError
        original_link(source_path, destination_path)

    monkeypatch.setattr(security.os, "link", race_link)

    with pytest.raises(LocalFileSecurityError) as raised:
        atomic_publish_fresh(source, destination, allowed_root=root)

    assert raised.value.code is LocalFileSecurityCode.DESTINATION_EXISTS
    assert destination.read_bytes() == b"winner"
    assert source.read_bytes() == b"ours"


def test_atomic_fresh_publication_moves_private_file(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    source = root / "source.tmp"
    destination = root / "final.txt"
    source.write_bytes(b"content")

    atomic_publish_fresh(source, destination, allowed_root=root)

    assert not source.exists()
    assert destination.read_bytes() == b"content"
    assert inspect_permission_status(destination, allowed_root=root) is PermissionStatus.PRIVATE_OWNER_ONLY


def test_checked_replacement_rejects_changed_destination(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    source = root / "source.tmp"
    destination = root / "index.sqlite"
    source.write_bytes(b"new")
    destination.write_bytes(b"old")
    expected = capture_secure_path(destination, allowed_root=root)
    destination.write_bytes(b"raced-content")

    with pytest.raises(LocalFileSecurityError) as raised:
        atomic_replace_checked(
            source,
            destination,
            allowed_root=root,
            expected_destination=expected,
        )

    assert raised.value.code is LocalFileSecurityCode.PATH_CHANGED
    assert destination.read_bytes() == b"raced-content"
    assert source.read_bytes() == b"new"


def test_pytest_temp_root_is_outside_repository(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[2]

    assert repository != tmp_path
    assert repository not in tmp_path.parents
