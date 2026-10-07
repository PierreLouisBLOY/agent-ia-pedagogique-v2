"""Exact R3-R5 code fabrication, never a substitute for active candidate checks."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from tests.support.r3_guard_oracle import PREPARATION

FABRICATION = "5b6f5630c54706bde7cc2afb72bd032efd289b9c"
ROOT = Path(__file__).resolve().parents[2]


def materialize_historical_guard_sources(destination: Path) -> Path:
    """Keep original Git objects; exclude private preparations from extraction/index.

    This is a synthetic test working tree of a declared historical fabrication.
    No candidate Python code is imported or executed. Private absence is not an
    attestation; the original documentary tests still inspect the actual checkout.
    """
    fabrication = FABRICATION

    def git(*args: str, cwd: Path = destination) -> bytes:
        return subprocess.run(["git", "-c", "safe.directory=" + str(cwd), *args],
                              cwd=cwd, check=True, capture_output=True).stdout

    git("clone", "--no-checkout", "--no-hardlinks", str(ROOT), str(destination), cwd=ROOT)
    git("config", "core.longpaths", "true")
    git("read-tree", fabrication)
    paths = git("ls-tree", "-r", "--name-only", "-z", fabrication).decode().split("\0")[:-1]
    selected = [p for p in paths if p not in PREPARATION]
    # checkout-index takes stdin, preserving paths exactly and excluding every
    # private preparation before any content is materialized.
    subprocess.run(["git", "checkout-index", "--stdin", "-z"], cwd=destination,
                   input=("\0".join(selected) + "\0").encode(), check=True, capture_output=True)
    private_index = sorted(set(paths) & set(PREPARATION))
    if private_index:
        git("update-index", "--force-remove", "--", *private_index)
    tree = git("write-tree").decode().strip()
    commit = git("-c", "user.name=Historical test fixture", "-c", "user.email=fixture@example.invalid",
                 "commit-tree", tree, "-p", fabrication, "-m",
                 "Synthetic historical code fixture; no private attestation").decode().strip()
    git("update-ref", "HEAD", commit)
    assert not set(git("ls-files", "-z").decode().split("\0")) & set(PREPARATION)
    assert not any((destination / p).exists() for p in PREPARATION)
    objects = {}
    for entry in git("ls-tree", "-r", "-z", fabrication).decode().split("\0")[:-1]:
        metadata, path = entry.split("\t", 1)
        objects[path] = metadata.split()[2]
    for path in selected:
        actual = (destination / path).read_bytes().replace(b"\r\n", b"\n")
        blob = b"blob " + str(len(actual)).encode() + b"\0" + actual
        assert hashlib.sha1(blob, usedforsecurity=False).hexdigest() == objects[path], path
    return destination
