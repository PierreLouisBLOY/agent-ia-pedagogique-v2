"""Application conversation boundary."""
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from backend.modules.work_orchestration.contracts.dto.conversation import ConversationCommand


@runtime_checkable
class ConversationInbound(Protocol):
    def snapshot(self) -> Mapping[str, object]: ...

    def execute(self, command: ConversationCommand) -> Mapping[str, object]: ...
