from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraft,
    ConversationDraftRequest,
)


@runtime_checkable
class ConversationGenerationPort(Protocol):
    def generate(self, *, request: ConversationDraftRequest) -> ConversationDraft: ...
