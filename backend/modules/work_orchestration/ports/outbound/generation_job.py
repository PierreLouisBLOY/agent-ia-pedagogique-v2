"""Bounded generation job; no process, SDK, credential or HTTP types."""
from dataclasses import dataclass
from typing import Protocol

from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraft,
    ConversationDraftRequest,
)


@dataclass(frozen=True, slots=True)
class GenerationJobResult:
    generation_id: str
    state: str
    draft: ConversationDraft | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.state not in {"CANDIDATE_READY", "FAILED_NO_EFFECT", "FAILED_OUTPUT", "UNKNOWN"}:
            raise ValueError("INVALID_JOB_RESULT")
        if (self.state == "CANDIDATE_READY") != (self.draft is not None):
            raise ValueError("INVALID_JOB_RESULT")


class GenerationJobPort(Protocol):
    def authorize(self, request: ConversationDraftRequest) -> None:
        """Fail closed before reservation if configuration, scope or budget is absent."""
        ...

    def start(self, request: ConversationDraftRequest) -> None: ...

    def poll(self) -> GenerationJobResult | None: ...

    def close(self) -> None: ...
