"""CAS publication of conversation and its optional immutable candidate."""
from typing import Protocol

from backend.modules.work_orchestration.contracts.dto.conversation import ConversationState
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView


class ConversationStore(Protocol):
    def read(self, conversation_id: str) -> ConversationState | None: ...

    def publish(self, state: ConversationState, *, expected_revision: int,
                production: ProductionReadView | None = None) -> None: ...
