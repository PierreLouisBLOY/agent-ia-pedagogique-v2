"""M04 creation only: no provider, transport, validation or promotion ownership."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraft,
    ConversationDraftRequest,
)
from backend.modules.pedagogical_design.ports.outbound.conversation_generation import (
    ConversationGenerationPort,
    ConversationPreparationPort,
)


@dataclass(frozen=True, slots=True)
class CreateConversationDraft:
    generation: ConversationGenerationPort

    def prepare(self, *, request: ConversationDraftRequest) -> Mapping[str, object]:
        if type(request) is not ConversationDraftRequest:
            raise TypeError("TYPED_DRAFT_REQUEST_REQUIRED")
        if not isinstance(self.generation, ConversationPreparationPort):
            raise TypeError("PREPARATION_PORT_REQUIRED")
        result = self.generation.prepare(request=request)
        if (set(result) != {"status", "projection", "references", "trace"}
                or result["status"] != "READY_NOT_SENT"):
            raise ValueError("INVALID_PREPARATION_RESULT")
        return result

    def create(self, *, request: ConversationDraftRequest) -> ConversationDraft:
        if type(request) is not ConversationDraftRequest:
            raise TypeError("TYPED_DRAFT_REQUEST_REQUIRED")
        result = self.generation.generate(request=request)
        if type(result) is not ConversationDraft:
            raise ValueError("INVALID_DRAFT_RESULT")
        return result
