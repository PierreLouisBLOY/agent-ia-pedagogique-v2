"""Retain F02 read handles for pilot source and preflight inputs; reject links and substitution."""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path

from mega_f02_windows_handles import Handle, _child, pin_directory


class RetainedInputs:
    def __init__(self, root: Path, paths: list[Path]) -> None:
        self.root = root
        self.paths = paths
        self.stack = ExitStack()

    def __enter__(self) -> RetainedInputs:
        try:
            base = pin_directory(self.root, self.stack)
            parents: dict[tuple[str, ...], Handle] = {(): base}
            for path in self.paths:
                relative = path.relative_to(self.root)
                parent = base
                for i, part in enumerate(relative.parts[:-1], 1):
                    prefix = relative.parts[:i]
                    if prefix not in parents:
                        handle = _child(parent, part, directory=True)
                        self.stack.callback(handle.close)
                        parents[prefix] = handle
                    parent = parents[prefix]
                handle = _child(parent, relative.name, directory=False)
                self.stack.callback(handle.close)
            return self
        except BaseException:
            self.stack.close()
            raise

    def __exit__(self, *args: object) -> None:
        self.stack.close()
