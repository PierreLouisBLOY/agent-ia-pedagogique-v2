"""Neutral P0 dispatch boundary. Normal offline composition leaves it unbound."""
from collections.abc import Mapping
from typing import Protocol


class P0GenerationPort(Protocol):
    def authorize(self, *, request: Mapping[str, object]) -> bool: ...

    def generate(self, *, request: Mapping[str, object]) -> Mapping[str, object]: ...
