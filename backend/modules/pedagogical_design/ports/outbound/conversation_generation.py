from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraft,
    ConversationDraftRequest,
)


@runtime_checkable
class ConversationGenerationPort(Protocol):
    def generate(self, *, request: ConversationDraftRequest) -> ConversationDraft: ...


@runtime_checkable
class ConversationPreparationPort(Protocol):
    def prepare(self, *, request: ConversationDraftRequest) -> Mapping[str, object]: ...
