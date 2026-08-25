from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.agent_runtime.agents.review.review_model import (
    ReviewPortRequest,
    ReviewPortResult,
)


@runtime_checkable
class ReviewPort(Protocol):
    def review(self, *, request: ReviewPortRequest) -> ReviewPortResult:
        ...
