from __future__ import annotations

from backend.agent_runtime.agents.review import (
    ReviewPortError,
    ReviewPortRequest,
    ReviewPortResult,
)


class RecordingReviewPort:
    """Single-result test double with no capability routing or retry."""

    def __init__(
        self,
        result: ReviewPortResult | None = None,
        error: ReviewPortError | None = None,
    ) -> None:
        if result is not None and error is not None:
            raise ValueError("result and error are mutually exclusive")
        self.result = result
        self.error = error
        self.calls: list[ReviewPortRequest] = []

    def review(self, *, request: ReviewPortRequest) -> ReviewPortResult:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise AssertionError("no test review result configured")
        return self.result
