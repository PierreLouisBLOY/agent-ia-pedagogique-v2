from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraft,
    ConversationDraftRequest,
)


@runtime_checkable
class CreateConversationDraftInbound(Protocol):
    def create(self, *, request: ConversationDraftRequest) -> ConversationDraft: ...
