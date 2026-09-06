"""Bounded generation job; no process, SDK, credential or HTTP types."""
from dataclasses import dataclass
from typing import Protocol

from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraft,
    ConversationDraftRequest,
)


@dataclass(frozen=True, slots=True)
class GenerationUsage:
    """Closed neutral technical evidence, never content or provider objects."""
    provider_attempted: bool = False
    response_received: bool = False
    parsing: str = "NOT_RUN"
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    cache_write_input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    service_tier: str = "UNKNOWN"

    def __post_init__(self) -> None:
        if (type(self.provider_attempted) is not bool or type(self.response_received) is not bool
                or (self.response_received and not self.provider_attempted)
                or self.parsing not in {"NOT_RUN", "SUCCEEDED", "FAILED", "REFUSED", "INCOMPLETE"}
                or self.service_tier not in {"UNKNOWN", "default", "flex", "priority", "scale", "ultrafast"}):
            raise ValueError("INVALID_GENERATION_USAGE")
        counters = (self.input_tokens, self.cached_input_tokens, self.cache_write_input_tokens,
                    self.output_tokens, self.total_tokens, self.reasoning_tokens)
        if any(v is not None and (type(v) is not int or not 0 <= v <= 10_000_000) for v in counters):
            raise ValueError("INVALID_GENERATION_USAGE")
        if not self.response_received and (any(v is not None for v in counters)
                                           or self.parsing != "NOT_RUN" or self.service_tier != "UNKNOWN"):
            raise ValueError("INVALID_GENERATION_USAGE")
        if (self.input_tokens is not None and any(v is not None and v > self.input_tokens
                for v in (self.cached_input_tokens, self.cache_write_input_tokens))) or (
                self.output_tokens is not None and self.reasoning_tokens is not None
                and self.reasoning_tokens > self.output_tokens):
            raise ValueError("INVALID_GENERATION_USAGE")


@dataclass(frozen=True, slots=True)
class GenerationJobResult:
    generation_id: str
    state: str
    draft: ConversationDraft | None = None
    error_code: str | None = None
    usage: GenerationUsage | None = None

    def __post_init__(self) -> None:
        if self.state not in {"CANDIDATE_READY", "FAILED_NO_EFFECT", "FAILED_OUTPUT", "UNKNOWN"}:
            raise ValueError("INVALID_JOB_RESULT")
        if (self.state == "CANDIDATE_READY") != (self.draft is not None):
            raise ValueError("INVALID_JOB_RESULT")
        if self.usage is not None and type(self.usage) is not GenerationUsage:
            raise ValueError("INVALID_JOB_RESULT")


class GenerationJobPort(Protocol):
    def authorize(self, request: ConversationDraftRequest) -> None:
        """Fail closed before reservation if configuration, scope or budget is absent."""
        ...

    def start(self, request: ConversationDraftRequest) -> None: ...

    def poll(self) -> GenerationJobResult | None: ...

    def close(self) -> None: ...
