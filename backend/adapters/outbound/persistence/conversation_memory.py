"""Real volatile store: atomic CAS, immutable exact versions, no filesystem."""
from __future__ import annotations

from threading import RLock

from backend.modules.work_orchestration.contracts.dto.conversation import (
    ConversationRejected,
    ConversationState,
)
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView


class ConversationMemoryStore:
    def __init__(self, initial: ConversationState) -> None:
        self._state = initial
        self._versions: dict[tuple[str, str], ProductionReadView] = {}
        self._lock = RLock()

    def read(self, conversation_id: str) -> ConversationState | None:
        with self._lock:
            return self._state if self._state.conversation_id == conversation_id else None

    def publish(self, state: ConversationState, *, expected_revision: int,
                production: ProductionReadView | None = None) -> None:
        with self._lock:
            if (state.conversation_id != self._state.conversation_id
                    or self._state.revision != expected_revision
                    or state.revision != expected_revision + 1):
                raise ConversationRejected("REVISION_CONFLICT")
            if production is not None:
                key = (production.production_ref, production.version_ref)
                old = self._versions.get(key)
                if production.conversation_id != state.conversation_id or (
                    old is not None and old != production
                ):
                    raise ConversationRejected("APPLICATION_FAILURE")
                if old is None and len(self._versions) >= 3:
                    raise ConversationRejected("SESSION_CAPACITY_REACHED")
                if state.view["current_candidate"] != {
                    "production_ref": key[0], "version_ref": key[1],
                }:
                    raise ConversationRejected("APPLICATION_FAILURE")
                self._versions[key] = production
            elif state.view["current_candidate"] != self._state.view["current_candidate"]:
                raise ConversationRejected("APPLICATION_FAILURE")
            self._state = state

    def read_version(self, *, conversation_id: str, production_ref: str,
                     version_ref: str) -> ProductionReadView | None:
        with self._lock:
            if conversation_id != self._state.conversation_id:
                return None
            return self._versions.get((production_ref, version_ref))

    def contains_production(self, *, conversation_id: str, production_ref: str) -> bool:
        with self._lock:
            return conversation_id == self._state.conversation_id and any(
                ref == production_ref for ref, _ in self._versions
            )
