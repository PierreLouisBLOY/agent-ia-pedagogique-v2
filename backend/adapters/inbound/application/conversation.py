"""Closed Application input boundary; HTTP sees no module or store internals."""
from collections.abc import Mapping
from typing import cast

from backend.modules.pedagogical_context.contracts.dto.conversation_context import ContextRejected
from backend.modules.work_orchestration.contracts.dto.conversation import (
    ConversationCommand,
    ConversationRejected,
    plain,
)
from backend.modules.work_orchestration.ports.inbound.conversation import ConversationInbound


class ConversationInputError(ValueError):
    def __init__(self, code: str, field_code: str | None = None) -> None:
        self.code, self.field_code = code, field_code
        super().__init__(code)


class ConversationApplicationInbound:
    def __init__(self, conversation: ConversationInbound) -> None:
        if not isinstance(conversation, ConversationInbound):
            raise TypeError("CONVERSATION_INBOUND_REQUIRED")
        self._conversation = conversation

    def snapshot(self) -> dict[str, object]:
        try:
            return cast(dict[str, object], plain(self._conversation.snapshot()))
        except ConversationRejected as error:
            raise ConversationInputError(error.code, error.field_code) from None

    def command(self, operation: str, body: Mapping[str, object]) -> dict[str, object]:
        try:
            command = ConversationCommand(operation, body)
            return cast(dict[str, object], plain(self._conversation.execute(command)))
        except ContextRejected as error:
            raise ConversationInputError("CONTEXT_INVALID", error.field) from None
        except ConversationRejected as error:
            raise ConversationInputError(error.code, error.field_code) from None
