"""Git-aware source inventory and metadata-only, non-destructive local retention audit.

This test/maintenance helper is not imported by the application runtime. It never
opens local artifact contents, follows directory links, or deletes anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

LOCAL_ROOTS = (
    ".tmp", "tmp", "temp", "artifacts", "runtime", "logs", "exports",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", ".venv", ".venv-validation", "venv",
)
FORBIDDEN_SUFFIXES = (
    ".sqlite", ".sqlite3", ".db", "-wal", "-shm", "-journal", ".bak", ".backup",
    ".bak.manifest.json", ".backup.manifest.json", ".tmp", ".building", ".jsonl",
    ".log", ".pyc", ".pyo", ".pem", ".key", ".exe", ".dll", ".whl", ".zip",
)


def repository_paths(root: Path, *, tracked_only: bool = False) -> tuple[str, ...]:
    """List source candidates, never walking ignored trees or nested test clones.

    The index is ALWAYS included: force-added ignored files cannot evade guards.
    Git failure is fatal, not a fallback to an empty (apparently clean) inventory.
    """
    command = ["git", "ls-files", "-z", "--cached"]
    if not tracked_only:
        command += ["--others", "--exclude-standard"]
    result = subprocess.run(command, cwd=root, check=True, capture_output=True)
    paths = result.stdout.decode("utf-8", errors="strict").split("\0")
    return tuple(sorted({path for path in paths if path}))


def forbidden_source_paths(paths: Iterable[str]) -> tuple[str, ...]:
    """Detect runtime/config/binary candidates by path only, including tracked ones."""
    offenders = []
    for path in paths:
        parts = PurePosixPath(path.lower()).parts
        name = parts[-1]
        if (
            name.endswith(FORBIDDEN_SUFFIXES)
            or name == "local.env"
            or name == ".env"
            or name.startswith(".env.")
            or any(part in {".tmp", ".venv", ".venv-validation", "__pycache__"}
                   for part in parts)
        ):
            offenders.append(path)
    return tuple(sorted(offenders))


def require_external_temp_root(path: Path, repository: Path) -> Path:
    resolved = path.resolve()
    root = repository.resolve()
    if resolved == root or resolved.is_relative_to(root):
        raise ValueError("Temporary output must remain outside the repository")
    return resolved


def _metadata_tree(path: Path, root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    pending = [path]
    while pending:
        current = pending.pop()
        relative = current.relative_to(root).as_posix()
        try:
            metadata = current.lstat()
            linked = stat.S_ISLNK(metadata.st_mode) or bool(
                getattr(metadata, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            )
            directory = stat.S_ISDIR(metadata.st_mode)
            records.append({
                "path": relative,
                "kind": "link_not_followed" if linked else "directory" if directory else "file",
                "size_bytes": metadata.st_size if not directory else 0,
                "mtime_ns": metadata.st_mtime_ns,
            })
            if directory and not linked:
                with os.scandir(current) as entries:
                    pending.extend(Path(entry.path) for entry in entries)
        except OSError as error:
            # Do not expose error messages or absolute machine paths.
            records.append({"path": relative, "kind": "unreadable_retained",
                            "error_type": type(error).__name__})
    return sorted(records, key=lambda record: (str(record["path"]), str(record["kind"])))


def retention_inventory(root: Path, *, older_than_days: int = 30) -> dict[str, object]:
    """Dry run: age is a review hint, never proof of safe removal or provenance."""
    if older_than_days < 0:
        raise ValueError("Retention review age must be non-negative")
    root = root.resolve()
    tracked = set(repository_paths(root, tracked_only=True))
    assigned: list[Path] = []
    for name in LOCAL_ROOTS:
        candidate = root / name
        if not candidate.exists():
            continue
        # Individually disposition every immediate historical .tmp item.
        if name == ".tmp" and candidate.is_dir() and not candidate.is_junction() \
                and not candidate.is_symlink():
            try:
                assigned.extend(candidate.iterdir())
            except OSError:
                assigned.append(candidate)
        else:
            assigned.append(candidate)
    # Bytecode caches next to source packages are also local, not source candidates.
    result = subprocess.run(
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard",
         "--directory", "-z"], cwd=root, check=True, capture_output=True,
    )
    for relative in result.stdout.decode("utf-8").split("\0"):
        if relative.rstrip("/").endswith("__pycache__"):
            candidate = root / relative
            if not any(candidate.is_relative_to(parent) for parent in assigned):
                assigned.append(candidate)
    now = datetime.now(UTC)
    items = []
    for path in sorted(set(assigned)):
        relative = path.relative_to(root).as_posix()
        records = _metadata_tree(path, root)
        tracked_children = sorted(p for p in tracked if p == relative or p.startswith(relative + "/"))
        ignored = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", "--", relative],
            cwd=root, check=False, capture_output=True,
        )
        if ignored.returncode not in (0, 1):
            raise RuntimeError("Cannot establish ignore disposition")
        mtimes = [int(str(r["mtime_ns"])) / 1e9 for r in records if "mtime_ns" in r]
        unreadable = sum(r["kind"] == "unreadable_retained" for r in records)
        cache = "cache" in relative or relative.startswith((".venv", "venv"))
        items.append({
            "path": relative,
            "git_status": "tracked" if tracked_children else "ignored" if ignored.returncode == 0 else "untracked",
            "category": "environment_or_cache" if cache else "historical_local_artifacts",
            "provenance": "local_path_classification_only_not_content_certified",
            "size_bytes": sum(int(str(r.get("size_bytes", 0))) for r in records),
            "file_count": sum(r["kind"] == "file" for r in records),
            "directory_count": sum(r["kind"] == "directory" for r in records),
            "unreadable_count": unreadable,
            "metadata_sha256": hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest(),
            "older_than_review_age": bool(mtimes) and max(mtimes) < now.timestamp() - older_than_days * 86400,
            "reproducible": "not_verified",
            "canonical_evidence": "tracked_paths_present" if tracked_children else "not_tracked_no_content_claim",
            "tracked_children": tracked_children,
            "runtime_required": "not_verified_no_deletion",
            "safe_to_remove": False,
            "should_be_ignored": not bool(tracked_children),
            "disposition": "RETAIN_UNKNOWN" if unreadable or tracked_children else "RETAIN_LOCAL_NO_DELETE_AUTHORITY",
            "finding_id": "CF-TEMP-LOCAL-001",
            "metadata": records,
        })
    return {"mode": "DRY_RUN_METADATA_ONLY", "deletion_count": 0,
            "review_age_days": older_than_days, "items": items}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--older-than-days", type=int, default=30)
    parser.add_argument("--output", type=Path, help="Optional report strictly outside the repository")
    args = parser.parse_args()
    output = require_external_temp_root(args.output, args.root) if args.output else None
    report = json.dumps(retention_inventory(args.root, older_than_days=args.older_than_days),
                        indent=2, ensure_ascii=True) + "\n"
    if output:
        with output.open("x", encoding="utf-8") as stream:
            stream.write(report)
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
