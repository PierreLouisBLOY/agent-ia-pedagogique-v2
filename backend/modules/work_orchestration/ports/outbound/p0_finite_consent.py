"""Application finite-chain decisions, independent of HTTP, SDK and runtime."""

from collections.abc import Callable, Mapping
from typing import Protocol


class P0FiniteConsentPort(Protocol):
    def preview(self, request: Mapping[str, object]) -> Mapping[str, object]: ...

    def finalize(
        self,
        *,
        request: Mapping[str, object],
        consent: Mapping[str, object],
        run: Callable[[], Mapping[str, object]],
    ) -> Mapping[str, object]: ...

    def revoke(self, preview_sha256: str) -> Mapping[str, object]: ...

    def observe(self, command_id: str) -> Mapping[str, object] | None: ...
